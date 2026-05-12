"""File upload and handling utilities."""

import tempfile
from pathlib import Path
from fastapi import HTTPException, UploadFile, status
import app.services.database as database_service


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


def resolve_target_cyclist_for_fit_upload(
    user: dict, cyclist_from_form: str | None
) -> tuple[str, Path]:
    """Resolve upload target cyclist and enforce access controls."""
    from app.services.authorization import is_admin, resolve_authorized_cyclist_and_dir

    if is_admin(user):
        cyclist_name = str(cyclist_from_form or "").strip()
        if not cyclist_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin must provide target cyclist.",
            )
        requested_cyclist, effective_dir = resolve_authorized_cyclist_and_dir(
            user, f"../DB/rides/{cyclist_name}"
        )
    else:
        requested_cyclist = database_service.get_or_assign_user_cyclist(str(user["id"]))
        effective_dir = f"../DB/rides/{requested_cyclist}"

    backend_dir = Path(__file__).resolve().parent.parent.parent  # Go up to backend/
    target_dir = (backend_dir / effective_dir).resolve()
    allowed_root = (backend_dir / "DB" / "rides").resolve()

    try:
        target_dir.relative_to(allowed_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only files under DB/rides are allowed",
        ) from exc

    target_dir.mkdir(parents=True, exist_ok=True)
    return requested_cyclist, target_dir
