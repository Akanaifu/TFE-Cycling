"""Strava account lifecycle management."""

import logging
import os
import time
from datetime import datetime, timedelta, timezone

import app.services.database as database_service
import app.services.strava as strava_service
from app.services.security import decrypt_secret_fernet

logger = logging.getLogger(__name__)

STRAVA_AUTO_DEAUTH_GC_INTERVAL_SECONDS = 3600
_strava_last_gc_ts = 0.0


def get_strava_auto_deauth_days() -> int:
    """Get auto-deauth TTL for Strava accounts (days)."""
    raw = os.getenv("STRAVA_AUTO_DEAUTH_DAYS", "90").strip()
    try:
        value = int(raw)
    except ValueError:
        return 90
    return max(0, value)


def is_account_stale(account: dict, max_age_days: int) -> bool:
    """Check if Strava account is older than max_age_days."""
    if max_age_days <= 0:
        return False
    updated_at = account.get("updated_at")
    if not isinstance(updated_at, datetime):
        return False
    now_utc = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return updated_at <= (now_utc - timedelta(days=max_age_days))


def deauthorize_and_clear_user_strava(user_id: str) -> dict[str, bool]:
    """Revoke Strava tokens and clear persisted data."""
    account = database_service.get_strava_account_for_user(user_id)
    if not account:
        return {"had_account": False, "remote_revoked": False}

    remote_revoked = False
    access_token_enc = str(account.get("access_token_enc") or "").strip()
    if access_token_enc:
        try:
            access_token = decrypt_secret_fernet(access_token_enc)
            strava_service.deauthorize_access_token(access_token)
            remote_revoked = True
        except (RuntimeError, ValueError, OSError, TypeError) as exc:
            logger.warning(
                "Strava remote deauthorization failed for user %s: %s", user_id, exc
            )

    database_service.delete_strava_account_for_user(user_id)
    return {"had_account": True, "remote_revoked": remote_revoked}


def enforce_user_strava_ttl(user_id: str, account: dict | None = None) -> bool:
    """Auto-deauth stale Strava account if TTL exceeded."""
    max_age_days = get_strava_auto_deauth_days()
    if max_age_days <= 0:
        return False

    current_account = account or database_service.get_strava_account_for_user(user_id)
    if not current_account:
        return False

    if not is_account_stale(current_account, max_age_days=max_age_days):
        return False

    result = deauthorize_and_clear_user_strava(user_id)
    logger.info(
        "Auto-deauthorized stale Strava account for user %s (age>%sd, remote_revoked=%s)",
        user_id,
        max_age_days,
        result["remote_revoked"],
    )
    return True


def run_strava_auto_deauth_gc() -> None:
    """Periodic garbage collection to deauth stale Strava accounts."""
    global _strava_last_gc_ts
    now_ts = time.time()
    if now_ts - _strava_last_gc_ts < STRAVA_AUTO_DEAUTH_GC_INTERVAL_SECONDS:
        return
    _strava_last_gc_ts = now_ts

    max_age_days = get_strava_auto_deauth_days()
    if max_age_days <= 0:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    try:
        stale_accounts = database_service.get_stale_strava_accounts(
            updated_before=cutoff,
            limit=200,
        )
    except (RuntimeError, ValueError, OSError, TypeError) as exc:
        logger.warning("Unable to list stale Strava accounts: %s", exc)
        return

    for account in stale_accounts:
        user_id = str(account.get("user_id") or "").strip()
        if not user_id:
            continue
        try:
            deauthorize_and_clear_user_strava(user_id)
        except (RuntimeError, ValueError, OSError, TypeError) as exc:
            logger.warning(
                "Unable to auto-deauthorize stale Strava account for user %s: %s",
                user_id,
                exc,
            )
