from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.services import email_verification as email_verification_service
import app.services.auth as auth_service
import app.services.database as database_service
from app.services.cookie_auth import set_auth_cookie, clear_auth_cookie
from app.services.utils import get_client_ip
from collections import defaultdict, deque
import time

router = APIRouter(prefix="/auth")

# Rate limiting for auth attempts
AUTH_RATE_LIMIT_WINDOW_SECONDS = 300
AUTH_RATE_LIMIT_MAX_ATTEMPTS = 8
_auth_attempts: dict[str, deque[float]] = defaultdict(deque)


class AuthLoginRequest(BaseModel):
    """Request payload for JWT login endpoint."""

    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class AuthRegisterRequest(BaseModel):
    """Request payload for user registration endpoint."""

    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    display_name: str = Field(default="")


class AuthVerifyEmailRequest(BaseModel):
    """Request payload for email verification endpoint."""

    email: str = Field(..., min_length=3)
    code: str = Field(..., min_length=6, max_length=6)


class AuthResendRequest(BaseModel):
    """Request payload to resend verification code."""

    email: str = Field(..., min_length=3)


def _enforce_auth_rate_limit(request: Request, email_hint: str = "") -> None:
    """Rate limit authentication attempts."""
    now = time.time()
    client_ip = get_client_ip(
        dict(request.headers), request.client.host if request.client else "unknown"
    )
    key = f"{client_ip}::{email_hint.strip().lower()}"
    bucket = _auth_attempts[key]

    while bucket and now - bucket[0] > AUTH_RATE_LIMIT_WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= AUTH_RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please retry later.",
        )

    bucket.append(now)


@router.post("/login")
async def auth_login(
    payload: AuthLoginRequest, request: Request, response: Response
) -> dict:
    """Authenticate a user and return a JWT access token."""
    _enforce_auth_rate_limit(request, payload.email)
    email = payload.email.strip().lower()
    user = database_service.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.get("email_verified_at"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not verified",
        )

    if not auth_service.verify_password(
        payload.password, str(user.get("password_hash", ""))
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = auth_service.create_access_token(
        user_id=str(user["id"]),
        email=str(user["email"]),
        role=str(user.get("role", "user")),
    )
    set_auth_cookie(response, token)
    return {
        "ok": True,
        "user": {
            "id": str(user["id"]),
            "email": str(user["email"]),
            "display_name": user.get("display_name"),
            "role": user.get("role", "user"),
        },
    }


@router.post("/verify-email")
async def auth_verify_email(payload: AuthVerifyEmailRequest, request: Request) -> dict:
    """Validate the code sent by email and activate the account."""
    _enforce_auth_rate_limit(request, payload.email)
    email = payload.email.strip().lower()
    user = database_service.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.get("email_verified_at"):
        return {"ok": True, "message": "Email already verified"}

    is_valid = email_verification_service.verify_code(
        user_id=str(user["id"]),
        code=payload.code,
    )
    if not is_valid:
        record = database_service.get_email_verification_request(str(user["id"]))
        if record and int(record.get("attempts_left") or 0) <= 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Verification code locked after 2 failed attempts",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    return {"ok": True, "message": "Email verified successfully"}


@router.post("/resend-verification")
async def auth_resend_verification(
    payload: AuthResendRequest, request: Request
) -> dict:
    """Resend the verification code to a user's email (if user exists).

    Enforce same auth rate limiting as other auth endpoints. Backend will
    apply server-side min-interval checks to avoid spam.
    """
    _enforce_auth_rate_limit(request, payload.email)
    email = payload.email.strip().lower()
    user = database_service.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.get("email_verified_at"):
        return {"ok": True, "message": "Email already verified"}

    try:
        email_verification_service.issue_verification_code(
            user_id=str(user["id"]),
            email=str(user["email"]),
            display_name=str(user.get("display_name", "")),
        )
    except RuntimeError as exc:
        msg = str(exc)
        if "Please wait" in msg or "recently sent" in msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=msg
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to resend verification email: {exc}",
        )
    except (ValueError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to resend verification email: {exc}",
        )

    return {"ok": True, "message": "Verification email resent. Check your inbox."}


@router.post("/register")
async def auth_register(
    payload: AuthRegisterRequest,
    request: Request,
) -> dict:
    """Register a new user account (open registration).
    - creates a new user with role `user` (not email-verified)
    - issues a verification code by email
    """
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

    # Create user (not verified)
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

    try:
        email_verification_service.issue_verification_code(
            user_id=str(user["id"]),
            email=str(user["email"]),
            display_name=str(user.get("display_name", "")),
        )
    except (RuntimeError, ValueError, OSError) as exc:
        database_service.delete_user_by_id(str(user["id"]))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to send verification email: {exc}",
        ) from exc

    return {
        "ok": True,
        "message": "User account created. Check your email for the verification code.",
        "user": {
            "id": str(user["id"]),
            "email": str(user["email"]),
            "display_name": user.get("display_name"),
            "role": user.get("role", "user"),
            "email_verified": False,
        },
    }


@router.post("/logout")
async def auth_logout(response: Response) -> dict:
    """Clear authentication cookie."""
    clear_auth_cookie(response)
    return {"ok": True}


@router.get("/me")
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
