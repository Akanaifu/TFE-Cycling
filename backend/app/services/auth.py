"""JWT authentication helpers and dependencies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
from typing import Any
from utils import _read_env
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.services import database as database_service

bearer_scheme = HTTPBearer(auto_error=False)


def _jwt_secret() -> str:
    secret = _read_env("JWT_SECRET_KEY", "")
    if not secret:
        raise ValueError("Missing JWT_SECRET_KEY in environment")
    if len(secret.encode("utf-8")) < 32:
        raise ValueError(
            "JWT_SECRET_KEY is too short. Use at least 32 bytes for HS256."
        )
    return secret


def _jwt_algorithm() -> str:
    return _read_env("JWT_ALGORITHM", "HS256") or "HS256"


def _jwt_expire_minutes() -> int:
    raw = _read_env("JWT_EXPIRE_MINUTES", "120")
    try:
        value = int(raw)
        return max(5, value)
    except ValueError:
        return 120


def _load_bcrypt() -> Any:
    try:
        return importlib.import_module("bcrypt")
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"Missing dependency bcrypt: {exc}") from exc


def _load_jwt() -> Any:
    try:
        return importlib.import_module("jwt")
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"Missing dependency PyJWT: {exc}") from exc


def verify_password(password_plain: str, password_stored: str) -> bool:
    """Verify password strictly against a bcrypt hash."""
    if not password_plain or not password_stored:
        return False

    stored = password_stored.strip()
    if not stored.startswith("$2"):
        return False

    bcrypt = _load_bcrypt()
    try:
        return bcrypt.checkpw(password_plain.encode("utf-8"), stored.encode("utf-8"))
    except ValueError:
        return False


def hash_password(password_plain: str) -> str:
    """Hash a password using bcrypt."""
    if not password_plain:
        raise ValueError("Password cannot be empty")

    bcrypt = _load_bcrypt()
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password_plain.encode("utf-8"), salt).decode("utf-8")


def create_access_token(*, user_id: str, email: str, role: str) -> str:
    jwt_mod = _load_jwt()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_jwt_expire_minutes())).timestamp()),
    }
    return jwt_mod.encode(payload, _jwt_secret(), algorithm=_jwt_algorithm())


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    user = database_service.get_user_by_email(email.strip().lower())
    if not user:
        return None

    if not user.get("email_verified_at"):
        return None

    if not verify_password(password, str(user.get("password_hash", ""))):
        return None
    return user


def _decode_token(token: str) -> dict[str, Any]:
    jwt_mod = _load_jwt()
    try:
        return jwt_mod.decode(token, _jwt_secret(), algorithms=[_jwt_algorithm()])
    except jwt_mod.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    *,
    request: Request,
) -> dict[str, Any]:
    token = ""
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif request is not None:
        token = str(request.cookies.get("tfe_access_token", "") or "").strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    payload = _decode_token(token)
    user_id = str(payload.get("sub", "") or "").strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = database_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


CurrentUser = Depends(get_current_user)
