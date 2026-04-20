"""FastAPI backend for TFE Cycling analysis.

Exposes REST endpoints for running HR/power prediction models on cycling rides.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import re
import tempfile
import time
import numpy as np
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from pydantic import BaseModel, Field
import app.services.auth as auth_service
import app.services.database as database_service
import app.services.fit_import as fit_import_service
import app.services.notebook as notebook_service
from app.services.security import decrypt_secret_fernet, encrypt_secret_fernet
import app.services.strava as strava_service


app = FastAPI(title="TFE Cycling API", version="0.1.0")


logger = logging.getLogger(__name__)


AUTH_RATE_LIMIT_WINDOW_SECONDS = 300
AUTH_RATE_LIMIT_MAX_ATTEMPTS = 8
_auth_attempts: dict[str, deque[float]] = defaultdict(deque)
MAX_FIT_UPLOAD_FILES = 20
MAX_FIT_UPLOAD_BYTES = 20 * 1024 * 1024


@app.on_event("startup")
async def startup_security_checks() -> None:
    """Fail fast if unsafe password hashes are present in users table."""
    try:
        insecure_users = database_service.get_users_with_non_bcrypt_hashes(limit=10)
    except Exception as exc:
        raise RuntimeError(
            f"Startup security check failed while validating password hashes: {exc}"
        ) from exc

    if insecure_users:
        preview = ", ".join(insecure_users)
        raise RuntimeError(
            "Unsafe users.password_hash values detected (non-bcrypt). "
            f"Update hashes before startup. Sample users: {preview}"
        )


# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tfe-cycling.vercel.app",
        "https://www.tfe-cycling.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class AnalysisRequest(BaseModel):
    """Request payload for analysis endpoint."""

    dir_path: str = Field(..., description="Directory containing PKL rides")
    selected_models_plot: list[str] = Field(
        default_factory=lambda: ["pred_arx_selected"]
    )
    selected_models_stats: list[str] = Field(
        default_factory=lambda: ["pred_arx_selected"]
    )
    show_rmse_table: bool = True
    prev_ride: int = 1
    nan_ratio: float = 1.0
    selected_train_ride: int = 1
    selected_target_rides: int | list[int] | None = None


class PklReadRequest(BaseModel):
    """Request payload for pickle readability test endpoint."""

    file_path: str = Field(..., description="Absolute or relative path to a .pkl file")


class PipelineRequest(BaseModel):
    """Request to run full pipeline with predictions and metadata."""

    dir_path: str = Field(..., description="Directory containing PKL rides")
    selected_models_compute: list[str] = Field(
        default_factory=lambda: ["pred_arx_selected"],
        description="Models to compute and return",
    )
    prev_ride: int = Field(default=1)
    nan_ratio: float = Field(default=1.0)
    selected_train_ride: int = Field(default=1)
    selected_target_rides: int | list[int] | None = Field(default=None)


class CompareModelsRequest(BaseModel):
    """Request to compare two models trained on different rides."""

    dir_path: str = Field(..., description="Directory containing PKL rides")
    train_ride_index_1: int = Field(
        ..., ge=1, description="1-based index for model 1 training ride"
    )
    train_ride_index_2: int = Field(
        ..., ge=1, description="1-based index for model 2 training ride"
    )
    test_ride_index: int = Field(..., ge=1, description="1-based index for test ride")
    apply_to_all_rides: bool = Field(
        default=False, description="Apply both models to all rides and compute diffs"
    )


class StravaExchangeCodeRequest(BaseModel):
    """Request payload to exchange Strava OAuth code."""

    code: str = Field(..., min_length=1, description="Strava OAuth code")
    state: str = Field(..., min_length=1, description="Signed OAuth state")


class AuthLoginRequest(BaseModel):
    """Request payload for JWT login endpoint."""

    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class AuthRegisterRequest(BaseModel):
    """Request payload for user registration endpoint."""

    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    display_name: str = Field(default="")


def _is_admin(user: dict) -> bool:
    return str(user.get("role", "")).strip().lower() == "admin"


def _extract_cyclist_from_dir_path(dir_path: str) -> str | None:
    normalized = (dir_path or "").replace("\\", "/")
    match = re.search(r"(cyclist\d+)", normalized)
    return match.group(1) if match else None


def _resolve_authorized_cyclist_and_dir(
    user: dict, requested_path: str
) -> tuple[str, str]:
    """Resolve and authorize cyclist from input, then return canonical rides dir.

    This blocks arbitrary tree traversal by ignoring raw path segments and only
    accepting cyclist names that exist in DB-backed visibility lists.
    """
    requested_cyclist = _extract_cyclist_from_dir_path(requested_path)
    if requested_cyclist is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cyclist path. Expected a cyclist like 'cyclist0'.",
        )

    if _is_admin(user):
        allowed_cyclists = set(database_service.get_all_cyclists_from_rides())
    else:
        allowed_cyclists = set(
            database_service.get_user_allowed_cyclists(str(user["id"]))
        )

    if requested_cyclist not in allowed_cyclists:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied for requested cyclist",
        )

    effective_dir = f"../DB/rides/{requested_cyclist}"
    return requested_cyclist, effective_dir


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce_auth_rate_limit(request: Request, email_hint: str = "") -> None:
    now = time.time()
    key = f"{_client_ip(request)}::{email_hint.strip().lower()}"
    bucket = _auth_attempts[key]

    while bucket and now - bucket[0] > AUTH_RATE_LIMIT_WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= AUTH_RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please retry later.",
        )

    bucket.append(now)


def _is_truthy_env(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_pkl_diagnostic_enabled() -> bool:
    return _is_truthy_env(os.getenv("ENABLE_PKL_DIAGNOSTIC", ""))


def _use_secure_cookie() -> bool:
    # In production, Secure cookies must be enabled by default.
    explicit = os.getenv("AUTH_COOKIE_SECURE", "").strip()
    if explicit:
        return _is_truthy_env(explicit)

    node_env = os.getenv("NODE_ENV", "").strip().lower()
    if node_env in {"development", "dev", "local"}:
        return False

    return True


def _trust_forwarded_headers() -> bool:
    return _is_truthy_env(os.getenv("TRUST_FORWARDED_HEADERS", "false"))


def _client_ip(request: Request) -> str:
    if _trust_forwarded_headers():
        forwarded_for = request.headers.get("x-forwarded-for", "").strip()
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="tfe_access_token",
        value=token,
        httponly=True,
        secure=_use_secure_cookie(),
        samesite="lax",
        max_age=60 * 60 * 2,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key="tfe_access_token",
        path="/",
        samesite="lax",
        secure=_use_secure_cookie(),
    )


def _resolve_target_cyclist_for_fit_upload(
    user: dict, cyclist_from_form: str | None
) -> tuple[str, Path]:
    """Resolve upload target cyclist and enforce role-based access controls."""
    if _is_admin(user):
        cyclist_name = str(cyclist_from_form or "").strip()
        if not cyclist_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin must provide target cyclist.",
            )
        requested_cyclist, effective_dir = _resolve_authorized_cyclist_and_dir(
            user, f"../DB/rides/{cyclist_name}"
        )
    else:
        allowed = database_service.get_user_allowed_cyclists(str(user["id"]))
        if len(allowed) == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "No cyclist folder is linked to your account yet. "
                    "Ask an admin to assign one first."
                ),
            )
        requested_cyclist = allowed[0]
        effective_dir = f"../DB/rides/{requested_cyclist}"

    backend_dir = Path(__file__).resolve().parent
    target_dir = (backend_dir / effective_dir).resolve()
    allowed_root = (backend_dir.parent / "DB" / "rides").resolve()

    try:
        target_dir.relative_to(allowed_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only files under DB/rides are allowed",
        ) from exc

    target_dir.mkdir(parents=True, exist_ok=True)
    return requested_cyclist, target_dir


async def _save_uploaded_fit_to_temp(upload: UploadFile, max_bytes: int) -> Path:
    """Persist uploaded FIT stream to a temp file with size enforcement."""
    temp_handle = tempfile.NamedTemporaryFile(suffix=".fit", delete=False)
    temp_path = Path(temp_handle.name)
    size = 0

    try:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large (> {max_bytes} bytes)",
                )
            temp_handle.write(chunk)

        temp_handle.flush()
        temp_handle.close()
        return temp_path
    except Exception:
        try:
            temp_handle.close()
        except Exception:
            pass
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
        raise
    finally:
        try:
            await upload.close()
        except Exception:
            pass


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint returning API status."""
    return {"message": "TFE Cycling backend is running"}


@app.get("/health")
async def health() -> dict:
    """Health check endpoint with DB connectivity status."""
    db_state = database_service.get_database_status()
    return {
        "status": "ok",
        "database": {
            "connected": db_state.get("connected", False),
        },
    }


@app.get("/db/status")
async def db_status(
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Detailed DB status for troubleshooting backend/database linkage."""
    _ = current_user
    db_state = database_service.get_database_status()
    if not db_state.get("connected"):
        raise HTTPException(status_code=503, detail=db_state)
    return {"ok": True, "db": db_state}


@app.post("/auth/login")
async def auth_login(
    payload: AuthLoginRequest, request: Request, response: Response
) -> dict:
    """Authenticate a user and return a JWT access token."""
    _enforce_auth_rate_limit(request, payload.email)
    user = auth_service.authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = auth_service.create_access_token(
        user_id=str(user["id"]),
        email=str(user["email"]),
        role=str(user.get("role", "user")),
    )
    _set_auth_cookie(response, token)
    return {
        "ok": True,
        "user": {
            "id": str(user["id"]),
            "email": str(user["email"]),
            "display_name": user.get("display_name"),
            "role": user.get("role", "user"),
        },
    }


@app.post("/auth/register")
async def auth_register(
    payload: AuthRegisterRequest, request: Request, response: Response
) -> dict:
    """Register a new user account."""
    _enforce_auth_rate_limit(request, payload.email)
    email = payload.email.strip().lower()

    # Check if email already exists
    existing = database_service.get_user_by_email(email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Hash password
    try:
        password_hash = auth_service.hash_password(payload.password)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password hashing failed: {exc}",
        ) from exc

    # Create user
    user = database_service.create_user(
        email=email,
        password_hash=password_hash,
        display_name=payload.display_name.strip(),
        role="user",
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )

    # Return token for immediate login
    token = auth_service.create_access_token(
        user_id=str(user["id"]),
        email=str(user["email"]),
        role=str(user.get("role", "user")),
    )
    _set_auth_cookie(response, token)

    return {
        "ok": True,
        "user": {
            "id": str(user["id"]),
            "email": str(user["email"]),
            "display_name": user.get("display_name"),
            "role": user.get("role", "user"),
        },
    }


@app.post("/auth/logout")
async def auth_logout(response: Response) -> dict:
    """Clear authentication cookie."""
    _clear_auth_cookie(response)
    return {"ok": True}


@app.get("/auth/me")
async def auth_me(current_user: dict = Depends(auth_service.get_current_user)) -> dict:
    """Return current authenticated user from JWT."""
    return {
        "ok": True,
        "user": {
            "id": str(current_user["id"]),
            "email": str(current_user["email"]),
            "display_name": current_user.get("display_name"),
            "role": current_user.get("role", "user"),
        },
    }


@app.get("/strava/status")
async def strava_status(
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Expose Strava env readiness and user-level Strava account status."""
    base_status = strava_service.get_strava_status()
    account = database_service.get_strava_account_for_user(str(current_user["id"]))

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
        },
    }


@app.get("/strava/auth-url")
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


@app.post("/strava/exchange-code")
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


@app.get("/strava/activities")
async def strava_get_activities(
    limit: int = Query(10, ge=1, le=100, description="Number of activities to fetch"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Fetch recent athlete activities from Strava API.

    Requires valid tokens persisted in PostgreSQL from exchange-code endpoint.
    Token refresh happens automatically if expired.
    """
    try:
        settings = strava_service.get_strava_settings()
        account = database_service.get_strava_account_for_user(str(current_user["id"]))
        if not account:
            raise ValueError("No Strava account connected for current user")

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
            # Preserve athlete data and update encrypted DB tokens
            new_tokens["athlete"] = tokens.get("athlete", {})

            database_service.update_strava_account_tokens(
                user_id=str(current_user["id"]),
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
        athlete_id = int(account.get("athlete_id") or 0)
        if athlete_id <= 0:
            raise ValueError("No athlete_id available for current Strava account")

        for activity in activities:
            try:
                activity_id = int(activity.get("id") or 0)
                if activity_id <= 0:
                    raise ValueError("Missing activity id")

                relative_path, absolute_path = (
                    database_service.build_strava_activity_file_path(
                        user_id=str(current_user["id"]),
                        athlete_id=athlete_id,
                        activity=activity,
                    )
                )

                streams = strava_service.get_activity_streams(
                    access_token=access_token,
                    activity_id=activity_id,
                )
                ride_df = strava_service.build_activity_dataframe(
                    activity=activity,
                    streams=streams,
                )

                absolute_path.parent.mkdir(parents=True, exist_ok=True)
                notebook_service.write_pickle_secure(ride_df, absolute_path)

                activity_with_path = dict(activity)
                activity_with_path["file_path"] = relative_path
                persisted_activities.append(activity_with_path)
            except Exception:
                failed_activities += 1

        if not persisted_activities:
            raise ValueError("Unable to persist any Strava activities")

        persistence = database_service.upsert_rides_from_strava_activities(
            user_id=str(current_user["id"]),
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
    except Exception as exc:
        logger.exception("Unable to fetch Strava activities")
        raise HTTPException(
            status_code=400,
            detail="Unable to fetch Strava activities.",
        ) from exc


@app.get("/cyclists/list")
async def get_cyclists_list(
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """List all available cyclists."""
    try:
        if _is_admin(current_user):
            cyclists = database_service.get_all_cyclists_from_rides()
        else:
            cyclists = database_service.get_user_allowed_cyclists(
                str(current_user["id"])
            )
        return {
            "ok": True,
            "cyclists": cyclists,
            "n_cyclists": len(cyclists),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to list cyclists: {exc}"
        ) from exc


@app.get("/rides/training-ride")
async def get_training_ride(
    cyclist: str = Query(..., description="Cyclist name (e.g., cyclist9)"),
    ride_index: int = Query(1, description="Ride index (1-based)"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Get a single training ride data."""
    try:
        if not _is_admin(current_user):
            allowed = set(
                database_service.get_user_allowed_cyclists(str(current_user["id"]))
            )
            if cyclist not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied for this cyclist",
                )

        get_single_ride_fn = getattr(notebook_service, "get_single_ride")
        return get_single_ride_fn(cyclist, ride_index)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to get ride: {exc}"
        ) from exc


@app.get("/rides/list")
async def list_rides(
    dir_path: str = Query(..., description="Directory path (relative or absolute)"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """List available rides in a directory with basic info."""
    try:
        requested_cyclist, effective_dir = _resolve_authorized_cyclist_and_dir(
            current_user, dir_path
        )

        rides = notebook_service.extract_donnee_pickle(effective_dir)
        ride_list = []
        for i, ride in enumerate(rides, start=1):
            datetime_label = ride.attrs.get("ride_datetime_label", "unknown")
            ride_list.append(
                {
                    "index": i,
                    "datetime": datetime_label,
                    "points": int(ride.shape[0]),
                    "columns": [str(c) for c in ride.columns.tolist()],
                }
            )
        return {
            "ok": True,
            "cyclist": requested_cyclist,
            "dir_path": str(effective_dir),
            "n_rides": len(rides),
            "rides": ride_list,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to list rides: {exc}"
        ) from exc


@app.post("/rides/import-fit")
async def import_fit_files(
    files: list[UploadFile] = File(..., description="One or many .fit files"),
    cyclist: str | None = Form(default=None),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Import one or many FIT files and save canonical PKL files under DB/rides."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded.",
        )

    if len(files) > MAX_FIT_UPLOAD_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files. Maximum is {MAX_FIT_UPLOAD_FILES}.",
        )

    target_cyclist, target_dir = _resolve_target_cyclist_for_fit_upload(
        current_user, cyclist
    )

    saved: list[dict[str, str | int]] = []
    skipped: list[dict[str, str]] = []

    for upload in files:
        original_name = str(upload.filename or "upload.fit").strip()
        if not original_name.lower().endswith(".fit"):
            skipped.append(
                {
                    "file": original_name,
                    "reason": "Only .fit files are accepted.",
                }
            )
            continue

        tmp_path: Path | None = None
        try:
            tmp_path = await _save_uploaded_fit_to_temp(
                upload, max_bytes=MAX_FIT_UPLOAD_BYTES
            )
            converted = fit_import_service.convert_fit_to_project_df(tmp_path)
            target_name = fit_import_service.convert_name_file(original_name)
            target_path = target_dir / target_name

            if target_path.exists():
                skipped.append(
                    {
                        "file": original_name,
                        "reason": f"Target file already exists: {target_name}",
                    }
                )
                continue

            notebook_service.write_pickle_secure(converted, target_path)
            saved.append(
                {
                    "source_file": original_name,
                    "saved_file": target_name,
                    "rows": int(converted.shape[0]),
                }
            )
        except HTTPException:
            raise
        except Exception as exc:
            skipped.append({"file": original_name, "reason": str(exc)})
        finally:
            try:
                if tmp_path is not None and tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

    return {
        "ok": True,
        "cyclist": target_cyclist,
        "saved_count": len(saved),
        "skipped_count": len(skipped),
        "saved": saved,
        "skipped": skipped,
    }


@app.post("/analysis/run")
async def run_analysis(
    payload: AnalysisRequest,
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Execute analysis on rides using specified configuration."""
    try:
        _, effective_dir = _resolve_authorized_cyclist_and_dir(
            current_user, payload.dir_path
        )

        config = notebook_service.AnalysisConfig(
            dir_path=effective_dir,
            selected_models_plot=payload.selected_models_plot,
            selected_models_stats=payload.selected_models_stats,
            show_rmse_table=payload.show_rmse_table,
            prev_ride=payload.prev_ride,
            nan_ratio=payload.nan_ratio,
            selected_train_ride=payload.selected_train_ride,
            selected_target_rides=payload.selected_target_rides,
        )
        return notebook_service.run_notebook_analysis(config)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/pipeline/run")
async def run_pipeline(
    payload: PipelineRequest,
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Execute full pipeline and return rides with predictions.

    Returns:
        dict with:
            - ok: bool
            - n_rides: number of rides in result
            - models_requested: list of models requested
            - models_computed: list of models actually computed
            - rides: list of rides with columns including predictions
                   Each ride includes: t, hr, po, t_min, work, work2, work3, work4, po_lag_*,
                   ride_datetime, and prediction columns
    """
    try:
        _, effective_dir = _resolve_authorized_cyclist_and_dir(
            current_user, payload.dir_path
        )

        rides = notebook_service.extract_donnee_pickle(effective_dir)
        if not rides:
            raise ValueError(f"No valid rides found in {effective_dir}")

        selected_models_compute = payload.selected_models_compute
        predictions: dict[str, list[pd.DataFrame]] = {}

        # Import prediction functions
        from app.services.notebook import (
            prediction_with_prev_rides,
            prediction,
            prediction_arx_with_prev_rides_no_fuite,
            prediction_arx_from_selected_ride,
        )

        # Compute requested models
        if "pred_hist" in selected_models_compute:
            predictions["pred_hist"] = prediction_with_prev_rides(
                [r.copy(deep=True) for r in rides],
                x_prev_rides=payload.prev_ride,
                max_nan_ratio=payload.nan_ratio,
            )

        if "pred_default" in selected_models_compute:
            predictions["pred_default"] = prediction([r.copy(deep=True) for r in rides])

        if "pred_no_fuite" in selected_models_compute:
            predictions["pred_no_fuite"] = prediction_arx_with_prev_rides_no_fuite(
                [r.copy(deep=True) for r in rides],
                x_prev_rides=payload.prev_ride,
                max_nan_ratio=payload.nan_ratio,
                init_window=5,
                n_hr_lags=1,
                ridge_alpha=5,
                po_lag_start=5,
            )

        if "pred_arx_selected" in selected_models_compute:
            predictions["pred_arx_selected"] = prediction_arx_from_selected_ride(
                [r.copy(deep=True) for r in rides],
                train_ride_index=payload.selected_train_ride,
                target_ride_indices=payload.selected_target_rides,
                n_hr_lags=1,
                ridge_alpha=5,
                po_lag_start=5,
                pred_col="arx_pred_selected",
                max_nan_ratio=payload.nan_ratio,
                init_window=5,
                one_based_index=True,
            )

        # Model specifications
        model_specs = {
            "pred_hist": {"col": "pred_prevx", "label": "pred_hist"},
            "pred_default": {"col": "pred1", "label": "pred_default"},
            "pred_no_fuite": {"col": "arx_pred", "label": "pred_no_fuite"},
            "pred_arx_selected": {
                "col": "arx_pred_selected",
                "label": "pred_arx_selected",
            },
        }

        # Check for unknown or missing models
        unknown = [m for m in selected_models_compute if m not in model_specs]
        if unknown:
            raise ValueError(f"Unknown models: {unknown}")

        missing = [m for m in selected_models_compute if m not in predictions]
        if missing:
            raise ValueError(f"Models not computed: {missing}")

        # Build combined rides with predictions
        rides_combined = []
        for i, ride in enumerate(rides):
            base = ride.copy()
            if "t_min" not in base.columns and "t" in base.columns:
                base["t_min"] = base["t"] / 60.0

            for model_key in selected_models_compute:
                spec = model_specs[model_key]
                src_ride = predictions[model_key][i]
                base[model_key] = src_ride[spec["col"]]

            rides_combined.append(base)

        # Convert rides to serializable format
        rides_serialized = []
        for ride in rides_combined:
            ride_dict = {
                "datetime": ride.attrs.get("ride_datetime_label", "unknown"),
                "n_points": int(ride.shape[0]),
                "columns": [str(c) for c in ride.columns.tolist()],
                "data": ride.to_dict(orient="records"),
            }
            rides_serialized.append(ride_dict)

        return {
            "ok": True,
            "n_rides": len(rides_combined),
            "models_requested": selected_models_compute,
            "models_computed": list(predictions.keys()),
            "rides": rides_serialized,
        }

    except Exception as exc:
        logger.exception("Pipeline run failed")
        raise HTTPException(
            status_code=400,
            detail="Pipeline failed.",
        ) from exc


@app.post("/pipeline/compare-models-trained")
async def compare_models_trained(
    payload: CompareModelsRequest,
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Compare two models trained on different rides, tested on a third ride.

    Trains model 1 on training_ride_1 and model 2 on training_ride_2,
    then applies both to test_ride_index. Optionally applies both models to all rides
    and computes the mean difference in BPM predictions.

    Formula for mean diff: sum(modeleA(t) - modeleB(t)) / nb_points
    """
    try:
        _, effective_dir = _resolve_authorized_cyclist_and_dir(
            current_user, payload.dir_path
        )

        # Import prediction functions
        from app.services.notebook import (
            prediction_arx_from_selected_ride,
        )

        # Load all rides
        rides = notebook_service.extract_donnee_pickle(effective_dir)
        if not rides:
            raise ValueError(f"No valid rides found in {effective_dir}")

        n_rides = len(rides)
        if payload.train_ride_index_1 < 1 or payload.train_ride_index_1 > n_rides:
            raise ValueError(
                f"train_ride_index_1 out of range: {payload.train_ride_index_1} (available: 1..{n_rides})"
            )
        if payload.train_ride_index_2 < 1 or payload.train_ride_index_2 > n_rides:
            raise ValueError(
                f"train_ride_index_2 out of range: {payload.train_ride_index_2} (available: 1..{n_rides})"
            )
        if payload.test_ride_index < 0 or payload.test_ride_index > n_rides:
            raise ValueError(
                f"test_ride_index out of range: {payload.test_ride_index} (available: 0..{n_rides})"
            )

        if payload.train_ride_index_1 == payload.train_ride_index_2:
            raise ValueError(
                "train_ride_index_1 and train_ride_index_2 must be different"
            )

        # Train model 1 on ride 1, test on test_ride
        rides_copy_1 = [r.copy(deep=True) for r in rides]
        pred_1_all = prediction_arx_from_selected_ride(
            rides_copy_1,
            train_ride_index=payload.train_ride_index_1,
            target_ride_indices=payload.test_ride_index,
            n_hr_lags=1,
            ridge_alpha=5,
            po_lag_start=5,
            pred_col="model_1_pred",
            max_nan_ratio=0.10,
            init_window=5,
            one_based_index=True,
        )

        # Train model 2 on ride 2, test on test_ride
        rides_copy_2 = [r.copy(deep=True) for r in rides]
        pred_2_all = prediction_arx_from_selected_ride(
            rides_copy_2,
            train_ride_index=payload.train_ride_index_2,
            target_ride_indices=payload.test_ride_index,
            n_hr_lags=1,
            ridge_alpha=5,
            po_lag_start=5,
            pred_col="model_2_pred",
            max_nan_ratio=0.10,
            init_window=5,
            one_based_index=True,
        )

        # Get test ride predictions (1-based index means we need index-1 for 0-based array)
        test_ride_zero_idx = payload.test_ride_index - 1
        test_ride_1 = pred_1_all[test_ride_zero_idx]
        test_ride_2 = pred_2_all[test_ride_zero_idx]

        # Extract predictions
        model1_preds = test_ride_1["model_1_pred"].tolist()
        model2_preds = test_ride_2["model_2_pred"].tolist()

        # Compute metrics on test ride
        def compute_metrics(actual, predicted):
            """Compute RMSE, MAE, R² for predictions."""
            actual_arr = np.array(actual, dtype=float)
            pred_arr = np.array(predicted, dtype=float)

            # Mask out NaN values
            mask = ~(np.isnan(actual_arr) | np.isnan(pred_arr))
            if not mask.any():
                return {"rmse": float("nan"), "mae": float("nan"), "r2": float("nan")}

            actual_clean = actual_arr[mask]
            pred_clean = pred_arr[mask]

            # RMSE
            rmse = float(np.sqrt(np.mean((actual_clean - pred_clean) ** 2)))

            # MAE
            mae = float(np.mean(np.abs(actual_clean - pred_clean)))

            # R²
            ss_res = np.sum((actual_clean - pred_clean) ** 2)
            ss_tot = np.sum((actual_clean - np.mean(actual_clean)) ** 2)
            r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else float("nan")

            return {"rmse": rmse, "mae": mae, "r2": r2}

        actual_hr = test_ride_1["hr"].tolist()
        metrics_1 = compute_metrics(actual_hr, model1_preds)
        metrics_2 = compute_metrics(actual_hr, model2_preds)

        # Prepare ride data response
        ride_data = {
            "datetime": test_ride_1.attrs.get("ride_datetime_label", "unknown"),
            "n_points": int(test_ride_1.shape[0]),
            "columns": [str(c) for c in test_ride_1.columns.tolist()],
            "data": test_ride_1.to_dict(orient="records"),
        }

        # If requested, apply both models to all rides and compute diffs
        all_rides_diffs = None
        if payload.apply_to_all_rides:
            # Train both models on all rides
            rides_copy_all_1 = [r.copy(deep=True) for r in rides]
            pred_all_1 = prediction_arx_from_selected_ride(
                rides_copy_all_1,
                train_ride_index=payload.train_ride_index_1,
                target_ride_indices=None,  # Apply to all
                n_hr_lags=1,
                ridge_alpha=5,
                po_lag_start=5,
                pred_col="model_1_pred",
                max_nan_ratio=0.10,
                init_window=5,
                one_based_index=True,
            )

            rides_copy_all_2 = [r.copy(deep=True) for r in rides]
            pred_all_2 = prediction_arx_from_selected_ride(
                rides_copy_all_2,
                train_ride_index=payload.train_ride_index_2,
                target_ride_indices=None,  # Apply to all
                n_hr_lags=1,
                ridge_alpha=5,
                po_lag_start=5,
                pred_col="model_2_pred",
                max_nan_ratio=0.10,
                init_window=5,
                one_based_index=True,
            )

            # Compute diffs for each ride
            all_rides_diffs = []
            for i, (r1, r2) in enumerate(zip(pred_all_1, pred_all_2), start=1):
                m1_preds = r1["model_1_pred"].to_numpy(dtype=float)
                m2_preds = r2["model_2_pred"].to_numpy(dtype=float)

                # Compute mean diff: sum(modeleA - modeleB) / nb_points
                valid_mask = ~(np.isnan(m1_preds) | np.isnan(m2_preds))
                if valid_mask.any():
                    diffs = m1_preds[valid_mask] - m2_preds[valid_mask]
                    mean_diff = float(np.mean(diffs))
                else:
                    mean_diff = 0.0

                all_rides_diffs.append(
                    {
                        "ride_index": i,
                        "datetime": r1.attrs.get("ride_datetime_label", "unknown"),
                        "n_points": int(r1.shape[0]),
                        "mean_bpm_diff": mean_diff,
                        "predictions": [
                            {
                                "model_1": (
                                    float(m1_preds[j])
                                    if np.isfinite(m1_preds[j])
                                    else None
                                ),
                                "model_2": (
                                    float(m2_preds[j])
                                    if np.isfinite(m2_preds[j])
                                    else None
                                ),
                                "diff": (
                                    float(m1_preds[j] - m2_preds[j])
                                    if np.isfinite(m1_preds[j])
                                    and np.isfinite(m2_preds[j])
                                    else None
                                ),
                            }
                            for j in range(len(m1_preds))
                        ],
                    }
                )

        return {
            "ok": True,
            "train_ride_1": payload.train_ride_index_1,
            "train_ride_2": payload.train_ride_index_2,
            "test_ride": payload.test_ride_index,
            "ride_data": ride_data,
            "model1_predictions": model1_preds,
            "model2_predictions": model2_preds,
            "metrics": {
                "rmse_model1": metrics_1["rmse"],
                "rmse_model2": metrics_2["rmse"],
                "mae_model1": metrics_1["mae"],
                "mae_model2": metrics_2["mae"],
                "r2_model1": metrics_1["r2"],
                "r2_model2": metrics_2["r2"],
            },
            "all_rides_diffs": all_rides_diffs,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Model comparison failed: {str(exc)}"
        ) from exc


@app.post("/pkl/test-read")
async def test_read_pkl(
    payload: PklReadRequest,
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Read a PKL file and return a minimal diagnostic payload (POST)."""
    if not _is_pkl_diagnostic_enabled() or not _is_admin(current_user):
        raise HTTPException(status_code=404, detail="Not found")
    return _read_pkl_diagnostic(payload.file_path)


@app.get("/pkl/test-read")
async def test_read_pkl_get(
    file_path: str = Query(..., description="Path to .pkl file"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Read a PKL file and return a minimal diagnostic payload (GET)."""
    if not _is_pkl_diagnostic_enabled() or not _is_admin(current_user):
        raise HTTPException(status_code=404, detail="Not found")
    return _read_pkl_diagnostic(file_path)


def _read_pkl_diagnostic(file_path: str) -> dict:
    """Shared PKL readability check used by GET and POST endpoints."""
    try:
        pkl_path = Path(file_path).expanduser()
        if not pkl_path.is_absolute():
            pkl_path = Path.cwd() / pkl_path
        pkl_path = pkl_path.resolve()

        allowed_root = (
            Path(__file__).resolve().parent.parent / "DB" / "rides"
        ).resolve()
        try:
            pkl_path.relative_to(allowed_root)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only files under DB/rides are allowed",
            ) from exc

        if not pkl_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {pkl_path}")

        if pkl_path.suffix.lower() != ".pkl":
            raise HTTPException(status_code=400, detail="Provided file is not a .pkl")

        data = notebook_service.load_pickle_secure(pkl_path)

        if isinstance(data, pd.DataFrame):
            return {
                "ok": True,
                "file_path": str(pkl_path),
                "type": "DataFrame",
                "rows": int(data.shape[0]),
                "columns": [str(c) for c in data.columns.tolist()],
            }

        return {
            "ok": True,
            "file_path": str(pkl_path),
            "type": type(data).__name__,
            "repr": repr(data)[:300],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"PKL read failed: {exc}") from exc
