"""Authentication cookie management."""

from fastapi import Response
from app.services.utils import use_secure_cookie


def set_auth_cookie(response: Response, token: str) -> None:
    """Set JWT access token in HTTP-only cookie."""
    response.set_cookie(
        key="tfe_access_token",
        value=token,
        httponly=True,
        secure=use_secure_cookie(),
        samesite="lax",
        max_age=60 * 60 * 2,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear authentication cookie."""
    response.delete_cookie(
        key="tfe_access_token",
        path="/",
        samesite="lax",
        secure=use_secure_cookie(),
    )
