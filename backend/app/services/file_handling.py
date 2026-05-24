"""File upload and handling utilities."""

import tempfile
from contextlib import suppress
from pathlib import Path
from fastapi import HTTPException, UploadFile, status
import app.services.database as database_service
from .storage_paths import get_cyclist_rides_dir, get_rides_root


async def save_uploaded_fit_to_temp(upload: UploadFile, max_bytes: int) -> Path:
    """Persist uploaded FIT stream to temp file with size enforcement."""
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
        with suppress(OSError):
            temp_handle.close()
        with suppress(OSError):
            if temp_path.exists():
                temp_path.unlink()
        raise
    finally:
        with suppress(Exception):
            await upload.close()


def resolve_target_cyclist_for_fit_upload(user: dict) -> tuple[str, Path]:
    """Resolve upload target cyclist and enforce access controls."""
    # FIT imports are always stored under the current user's mapped cyclist.
    requested_cyclist = database_service.get_or_assign_user_cyclist(str(user["id"]))
    target_dir = get_cyclist_rides_dir(requested_cyclist).resolve()
    allowed_root = get_rides_root().resolve()
    try:
        target_dir.relative_to(allowed_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only files under DB/rides are allowed",
        ) from exc

    target_dir.mkdir(parents=True, exist_ok=True)
    return requested_cyclist, target_dir
