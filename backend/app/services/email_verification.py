"""Email verification helpers and Apprise delivery for new user signup."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from pathlib import Path
import secrets

from apprise import Apprise
from typing import Any

from app.services import database as database_service

CODE_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _read_env_file() -> dict[str, str]:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return {}

    parsed: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def _read_env(name: str, default: str = "") -> str:
    file_env = _read_env_file()
    if name in file_env and file_env[name] != "":
        value = file_env[name]
    else:
        value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else str(value)


def _read_bool_env(name: str, default: bool = False) -> bool:
    raw = _read_env(name, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "on"}


def _read_int_env(name: str, default: int) -> int:
    raw = _read_env(name, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


def _verification_secret() -> str:
    secret = _read_env("MAIL_VERIFICATION_SECRET", "")
    if not secret:
        raise ValueError("Missing MAIL_VERIFICATION_SECRET in environment")
    return secret


def generate_verification_code(length: int = 6) -> str:
    if length <= 0:
        raise ValueError("Code length must be positive")
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def _normalize_code(code: str) -> str:
    return "".join(ch for ch in str(code or "").upper().strip() if ch.isalnum())


def hash_verification_code(code: str) -> str:
    normalized = _normalize_code(code)
    if len(normalized) != 6:
        raise ValueError(
            "Verification code must contain exactly 6 alphanumeric characters"
        )
    payload = f"{_verification_secret()}:{normalized}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _apprise_urls() -> list[str]:
    raw_urls = _read_env("APPRISE_URL", "")
    urls = [line.strip() for line in raw_urls.replace(";", "\n").splitlines()]
    return [url for url in urls if url]


def build_verification_email_body(
    *, display_name: str, code: str, expires_in_minutes: int
) -> str:
    recipient = display_name.strip() or "Bonjour"
    return (
        f"{recipient},\n\n"
        "Voici ton code de vérification pour activer ton compte TFE Cycling :\n\n"
        f"{code}\n\n"
        f"Ce code est valable pendant {expires_in_minutes} minutes et tu n'as que 2 essais.\n"
        "Si tu n'as pas demandé cette création de compte, tu peux ignorer ce message.\n"
    )


def send_verification_email(*, to_email: str, display_name: str, code: str) -> None:
    expires_in_minutes = _read_int_env("MAIL_VERIFICATION_EXPIRE_MINUTES", 10)

    title = "Ton code de vérification TFE Cycling"
    body = build_verification_email_body(
        display_name=display_name, code=code, expires_in_minutes=expires_in_minutes
    )

    a = Apprise()
    urls = _apprise_urls()
    if not urls:
        raise ValueError("Missing APPRISE_URL or APPRISE_URLS in environment")

    for url in urls:
        url = f"{url}&to={to_email}"
        if not a.add(url):
            raise ValueError(f"Invalid Apprise URL: {url}")

    if not a.notify(title=title, body=body):
        raise RuntimeError("Apprise did not send the verification email")


def issue_verification_code(
    *, user_id: str, email: str, display_name: str = ""
) -> dict[str, Any]:
    code = generate_verification_code(6)
    expires_in_minutes = _read_int_env("MAIL_VERIFICATION_EXPIRE_MINUTES", 10)
    attempts_left = _read_int_env("MAIL_VERIFICATION_MAX_ATTEMPTS", 2)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
    record = database_service.create_email_verification_request(
        user_id=user_id,
        email=email,
        code_hash=hash_verification_code(code),
        expires_at=expires_at,
        attempts_left=attempts_left,
    )
    send_verification_email(to_email=email, display_name=display_name, code=code)
    return {
        "verification": record,
        "expires_at": expires_at,
        "attempts_left": attempts_left,
    }


def verify_code(*, user_id: str, code: str) -> bool:
    record = database_service.get_email_verification_request(user_id)
    if not record:
        return False

    if record.get("verified_at"):
        return True

    expires_at = record.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if isinstance(expires_at, datetime) and expires_at < datetime.now(timezone.utc):
        return False

    attempts_left = int(record.get("attempts_left") or 0)
    if attempts_left <= 0:
        return False

    expected_hash = str(record.get("code_hash") or "")
    provided_hash = hash_verification_code(code)
    if not hmac.compare_digest(expected_hash, provided_hash):
        database_service.decrement_email_verification_attempt(user_id)
        return False

    database_service.mark_user_email_verified(user_id)
    return True
