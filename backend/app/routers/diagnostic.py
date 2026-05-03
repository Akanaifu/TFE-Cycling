"""Health check and diagnostic routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from pathlib import Path
import logging

import app.services.auth as auth_service
import app.services.database as database_service
import app.services.notebook as notebook_service
from app.services.utils import is_pkl_diagnostic_enabled
from app.services.authorization import is_admin

logger = logging.getLogger(__name__)

router = APIRouter()


class PklReadRequest(BaseModel):
    """Request payload for pickle readability test endpoint."""

    file_path: str = Field(..., description="Absolute or relative path to a .pkl file")


@router.get("/api")
async def root() -> dict[str, str]:
    """Root endpoint returning API status."""
    return {"message": "TFE Cycling backend is running"}


@router.get("/health")
async def health() -> dict:
    """Health check endpoint with DB connectivity status."""
    db_state = database_service.get_database_status()
    return {
        "status": "ok",
        "database": {
            "connected": db_state.get("connected", False),
        },
    }


@router.get("/db/status")
async def db_status(
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Detailed DB status for troubleshooting backend/database linkage."""
    _ = current_user
    db_state = database_service.get_database_status()
    if not db_state.get("connected"):
        raise HTTPException(status_code=503, detail=db_state)
    return {"ok": True, "db": db_state}


@router.post("/pkl/test-read")
async def test_read_pkl(
    payload: PklReadRequest,
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Read a PKL file and return a minimal diagnostic payload (POST)."""
    if not is_pkl_diagnostic_enabled() or not is_admin(current_user):
        raise HTTPException(status_code=404, detail="Not found")
    return _read_pkl_diagnostic(payload.file_path)


@router.get("/pkl/test-read")
async def test_read_pkl_get(
    file_path: str = Query(..., description="Path to .pkl file"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Read a PKL file and return a minimal diagnostic payload (GET)."""
    if not is_pkl_diagnostic_enabled() or not is_admin(current_user):
        raise HTTPException(status_code=404, detail="Not found")
    return _read_pkl_diagnostic(file_path)


def _read_pkl_diagnostic(file_path: str) -> dict:
    """Shared PKL readability check used by GET and POST endpoints."""
    try:
        pkl_path = Path(file_path).expanduser()
        if not pkl_path.is_absolute():
            pkl_path = Path.cwd() / pkl_path
        pkl_path = pkl_path.resolve()

        allowed_root = (
            Path(__file__).resolve().parent.parent.parent / "DB" / "rides"
        ).resolve()
        try:
            pkl_path.relative_to(allowed_root)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only files under DB/rides are allowed",
            ) from exc

        if not pkl_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {pkl_path}")

        if pkl_path.suffix.lower() != ".pkl":
            raise HTTPException(status_code=400, detail="Provided file is not a .pkl")

        data = notebook_service.load_pickle_secure(pkl_path)

        if isinstance(data, __import__("pandas").DataFrame):
            return {
                "ok": True,
                "file_path": str(pkl_path),
                "type": "DataFrame",
                "shape": list(data.shape),
                "columns": [str(c) for c in data.columns.tolist()],
            }

        return {
            "ok": True,
            "file_path": str(pkl_path),
            "type": type(data).__name__,
            "repr": repr(data)[:300],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"PKL read failed: {exc}") from exc
