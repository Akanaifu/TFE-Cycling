"""Ride data and FIT file upload routes."""

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
import logging

import app.services.auth as auth_service
import app.services.database as database_service
import app.services.fit_import as fit_import_service
import app.services.notebook as notebook_service
from app.services.authorization import is_admin, resolve_authorized_cyclist_and_dir
from app.services.file_handling import (
    convert_uploaded_fit_to_project_df,
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
    if not is_admin(current_user):
        allowed = set(database_service.get_user_allowed_cyclists(str(current_user["id"])))
        if cyclist not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied for this cyclist",
            )

    get_single_ride_fn = getattr(notebook_service, "get_single_ride")
    return get_single_ride_fn(cyclist, ride_index)


@router.get("/list")
async def list_rides(
    dir_path: str = Query(..., description="Directory path (relative or absolute)"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """List available rides in a directory with basic info."""
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


@router.post("/import-fit")
async def import_fit_files(
    files: list[UploadFile] = File(..., description="One or many .fit files"),
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

    target_cyclist, target_dir = resolve_target_cyclist_for_fit_upload(current_user)
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

        converted, import_error = await convert_uploaded_fit_to_project_df(
            upload, MAX_FIT_UPLOAD_BYTES
        )
        if import_error:
            skipped.append({"file": original_name, "reason": import_error})
            continue

        assert converted is not None
        target_name = fit_import_service.convert_name_file(original_name)
        target_path = target_dir / target_name

        if not notebook_service.has_hr_or_power_signal(converted):
            skipped.append(
                {
                    "file": original_name,
                    "reason": "Ride has no heart rate nor power data.",
                }
            )
            continue

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

    return {
        "ok": True,
        "cyclist": target_cyclist,
        "saved_count": len(saved),
        "skipped_count": len(skipped),
        "saved": saved,
        "skipped": skipped,
    }
