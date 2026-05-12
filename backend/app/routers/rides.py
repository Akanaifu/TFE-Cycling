"""Ride data and FIT file upload routes."""

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
import logging
from pathlib import Path

import app.services.auth as auth_service
import app.services.database as database_service
import app.services.fit_import as fit_import_service
import app.services.notebook as notebook_service
from app.services.authorization import is_admin, resolve_authorized_cyclist_and_dir
from app.services.file_handling import (
    save_uploaded_fit_to_temp,
    resolve_target_cyclist_for_fit_upload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rides")

MAX_FIT_UPLOAD_FILES = 20
MAX_FIT_UPLOAD_BYTES = 20 * 1024 * 1024


@router.get("/training-ride")
async def get_training_ride(
    cyclist: str = Query(..., description="Cyclist name (e.g., cyclist9)"),
    ride_index: int = Query(1, description="Ride index (1-based)"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Get a single training ride data."""
    try:
        if not is_admin(current_user):
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
        if "No readable pickle files found" in str(exc):
            raise HTTPException(status_code=400, detail="Le dossier est vide.") from exc
        raise HTTPException(
            status_code=400, detail=f"Failed to get ride: {exc}"
        ) from exc


@router.get("/list")
async def list_rides(
    dir_path: str = Query(..., description="Directory path (relative or absolute)"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """List available rides in a directory with basic info."""
    try:
        requested_cyclist, effective_dir = resolve_authorized_cyclist_and_dir(
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


@router.post("/import-fit")
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

    target_cyclist, target_dir = resolve_target_cyclist_for_fit_upload(
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
            tmp_path = await save_uploaded_fit_to_temp(
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
