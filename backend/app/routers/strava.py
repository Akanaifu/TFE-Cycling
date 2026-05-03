"""Strava OAuth and activity routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
import logging

import app.services.auth as auth_service
import app.services.database as database_service
import app.services.strava as strava_service
import app.services.notebook as notebook_service
from app.services.security import decrypt_secret_fernet, encrypt_secret_fernet
from app.services.strava_lifecycle import (
    deauthorize_and_clear_user_strava,
    enforce_user_strava_ttl,
    get_strava_auto_deauth_days,
    run_strava_auto_deauth_gc,
)
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strava")


class StravaExchangeCodeRequest(BaseModel):
    """Request payload to exchange Strava OAuth code."""

    code: str = Field(..., min_length=1, description="Strava OAuth code")
    state: str = Field(..., min_length=1, description="Signed OAuth state")


@router.get("/status")
async def strava_status(
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Expose Strava env readiness and user-level Strava account status."""
    run_strava_auto_deauth_gc()

    base_status = strava_service.get_strava_status()
    current_user_id = str(current_user["id"])
    account = database_service.get_strava_account_for_user(current_user_id)
    auto_deauthorized = enforce_user_strava_ttl(current_user_id, account=account)
    if auto_deauthorized:
        account = None

    athlete_id = account.get("athlete_id") if account else None
    expires_at = account.get("expires_at") if account else None
    has_db_tokens = bool(account and account.get("access_token_enc"))

    return {
        "ok": True,
        "status": {
            **base_status,
            "connected": has_db_tokens,
            "athlete_id": athlete_id,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "auto_deauthorized": auto_deauthorized,
            "auto_deauth_days": get_strava_auto_deauth_days(),
        },
    }


@router.post("/deauthorize")
async def strava_deauthorize(
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Revoke Strava access for current user and clear persisted tokens."""
    try:
        user_id = str(current_user["id"])
        result = deauthorize_and_clear_user_strava(user_id)
        return {
            "ok": True,
            "result": {
                "had_account": result["had_account"],
                "remote_revoked": result["remote_revoked"],
            },
        }
    except Exception as exc:
        logger.exception("Unable to deauthorize Strava account")
        raise HTTPException(
            status_code=400,
            detail="Unable to deauthorize Strava account.",
        ) from exc


@router.get("/auth-url")
async def strava_auth_url(
    state: str | None = Query(None, description="Optional client nonce"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Build Strava OAuth authorization URL from env settings."""
    try:
        oauth_state = strava_service.build_oauth_state_token(
            user_id=str(current_user["id"]),
            nonce=state,
        )
        url = strava_service.build_authorization_url(state=oauth_state)
        return {"ok": True, "auth_url": url, "oauth_state": oauth_state}
    except Exception as exc:
        logger.exception("Unable to build Strava auth URL")
        raise HTTPException(
            status_code=400,
            detail="Unable to build Strava auth URL.",
        ) from exc


@router.post("/exchange-code")
async def strava_exchange_code(
    payload: StravaExchangeCodeRequest,
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Exchange OAuth code and persist encrypted tokens in PostgreSQL."""
    try:
        if not strava_service.validate_oauth_state_token(
            payload.state,
            user_id=str(current_user["id"]),
            max_age_seconds=900,
        ):
            raise ValueError("Invalid OAuth state")

        raw_payload = strava_service.exchange_code_for_tokens_payload(payload.code)
        encrypted = strava_service.build_encrypted_tokens_payload(raw_payload)

        athlete = raw_payload.get("athlete") if isinstance(raw_payload, dict) else None
        athlete_id = athlete.get("id") if isinstance(athlete, dict) else None
        if athlete_id is None:
            raise ValueError("Token payload missing athlete.id")

        settings = strava_service.get_strava_settings()
        scope = str(raw_payload.get("scope") or settings.get("scopes") or "")

        database_service.upsert_strava_account_for_user(
            user_id=str(current_user["id"]),
            athlete_id=int(athlete_id),
            access_token_enc=str(encrypted["access_token_enc"]),
            refresh_token_enc=str(encrypted["refresh_token_enc"]),
            expires_at=(
                int(raw_payload.get("expires_at"))
                if raw_payload.get("expires_at") is not None
                else None
            ),
            scope=scope,
        )

        return {
            "ok": True,
            "result": {
                "saved": True,
                "storage": "database",
                "token_type": raw_payload.get("token_type", "Bearer"),
                "expires_at": raw_payload.get("expires_at"),
                "athlete_id": athlete_id,
            },
        }
    except Exception as exc:
        logger.exception("Unable to exchange Strava code")
        raise HTTPException(
            status_code=400,
            detail="Unable to exchange Strava code.",
        ) from exc


@router.get("/activities")
async def strava_get_activities(
    limit: int = Query(10, ge=1, le=100, description="Number of activities to fetch"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Fetch recent athlete activities from Strava API.

    Requires valid tokens persisted in PostgreSQL from exchange-code endpoint.
    Token refresh happens automatically if expired.
    """
    try:
        run_strava_auto_deauth_gc()

        settings = strava_service.get_strava_settings()
        current_user_id = str(current_user["id"])
        account = database_service.get_strava_account_for_user(current_user_id)
        if not account:
            raise ValueError("No Strava account connected for current user")

        if enforce_user_strava_ttl(current_user_id, account=account):
            raise ValueError(
                "Strava access expired automatically. Reconnect your account."
            )

        tokens = {
            "access_token": decrypt_secret_fernet(str(account["access_token_enc"])),
            "refresh_token": decrypt_secret_fernet(str(account["refresh_token_enc"])),
            "expires_at": (
                int(account["expires_at"].replace(tzinfo=timezone.utc).timestamp())
                if isinstance(account.get("expires_at"), datetime)
                else None
            ),
            "athlete": {"id": account.get("athlete_id")},
        }

        # Check and refresh if needed
        if strava_service.is_token_expired(tokens):
            new_tokens = strava_service.refresh_tokens(
                settings["client_id"],
                settings["client_secret"],
                tokens.get("refresh_token", ""),
            )
            new_tokens["athlete"] = tokens.get("athlete", {})

            database_service.update_strava_account_tokens(
                user_id=current_user_id,
                access_token_enc=encrypt_secret_fernet(
                    str(new_tokens.get("access_token", ""))
                ),
                refresh_token_enc=encrypt_secret_fernet(
                    str(new_tokens.get("refresh_token", ""))
                ),
                expires_at=(
                    int(new_tokens.get("expires_at"))
                    if new_tokens.get("expires_at") is not None
                    else None
                ),
            )
            tokens = new_tokens

        access_token = tokens.get("access_token")
        if not access_token:
            raise ValueError("No access token in persisted tokens")

        activities = strava_service.get_athlete_activities(
            access_token=access_token, limit=limit
        )

        persisted_activities: list[dict[str, object]] = []
        failed_activities = 0
        activity_errors: list[str] = []
        athlete_id = int(account.get("athlete_id") or 0)
        if athlete_id <= 0:
            raise ValueError("No athlete_id available for current Strava account")

        for activity in activities:
            activity_id = int(activity.get("id") or 0)
            try:
                if activity_id <= 0:
                    raise ValueError("Missing activity id")

                stored_file_name, absolute_path = (
                    database_service.build_strava_activity_file_path(
                        user_id=str(current_user["id"]),
                        athlete_id=athlete_id,
                        activity=activity,
                    )
                )

                try:
                    streams = strava_service.get_activity_streams(
                        access_token=access_token,
                        activity_id=activity_id,
                    )
                except ValueError as exc:
                    logger.warning(
                        "Strava streams fetch failed for activity %s: %s",
                        activity_id,
                        exc,
                    )
                    activity_errors.append(
                        f"activity {activity_id}: streams fetch failed"
                    )
                    streams = {}

                ride_df = strava_service.build_activity_dataframe(
                    activity=activity,
                    streams=streams,
                )

                absolute_path.parent.mkdir(parents=True, exist_ok=True)
                notebook_service.write_pickle_secure(ride_df, absolute_path)

                activity_with_path = dict(activity)
                activity_with_path["file_path"] = stored_file_name
                persisted_activities.append(activity_with_path)
            except (ValueError, RuntimeError, OSError, TypeError) as exc:
                failed_activities += 1
                activity_errors.append(f"activity {activity_id}: {exc}")
                logger.exception("Failed to persist Strava activity %s", activity_id)

        if not persisted_activities:
            error_summary = "; ".join(activity_errors[:3])
            if error_summary:
                raise ValueError(
                    "Unable to persist any Strava activities. "
                    f"Sample errors: {error_summary}"
                )
            raise ValueError("Unable to persist any Strava activities")

        persistence = database_service.upsert_rides_from_strava_activities(
            user_id=current_user_id,
            strava_account_id=str(account["id"]),
            athlete_id=athlete_id,
            activities=persisted_activities,
        )

        return {
            "ok": True,
            "n_activities": len(activities),
            "activities": activities,
            "written_count": len(persisted_activities),
            "saved_count": int(persistence.get("saved_count", 0)),
            "created_count": int(persistence.get("created_count", 0)),
            "updated_count": int(persistence.get("updated_count", 0)),
            "skipped_count": int(persistence.get("skipped_count", 0)),
            "failed_count": failed_activities,
        }
    except ValueError as exc:
        logger.exception("Unable to fetch Strava activities")
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except (RuntimeError, OSError, TypeError) as exc:
        logger.exception("Unable to fetch Strava activities")
        raise HTTPException(
            status_code=500,
            detail="Unable to fetch Strava activities.",
        ) from exc
