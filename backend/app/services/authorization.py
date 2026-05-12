"""Authorization and cyclist access control utilities."""

import re
from fastapi import HTTPException, status
import app.services.database as database_service


def is_admin(user: dict) -> bool:
    """Check if user has admin role."""
    return str(user.get("role", "")).strip().lower() == "admin"


def extract_cyclist_from_dir_path(dir_path: str) -> str | None:
    """Extract cyclist name from a directory path (e.g., 'cyclist0' from '.../cyclist0')."""
    normalized = (dir_path or "").replace("\\", "/")
    match = re.search(r"(cyclist\d+)", normalized)
    return match.group(1) if match else None


def resolve_authorized_cyclist_and_dir(
    user: dict, requested_path: str
) -> tuple[str, str]:
    """Resolve and authorize cyclist from path, returning canonical rides dir.

    This blocks arbitrary tree traversal by validating cyclist names against
    DB-backed visibility lists.

    Args:
        user: Current user dict from auth
        requested_path: Path containing cyclist name

    Returns:
        (cyclist_name, effective_directory_path)

    Raises:
        HTTPException: If path invalid or access denied
    """
    requested_cyclist = extract_cyclist_from_dir_path(requested_path)
    if requested_cyclist is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cyclist path. Expected a cyclist like 'cyclist0'.",
        )

    if is_admin(user):
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
