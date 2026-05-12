"""Cyclist data routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
import logging

import app.services.auth as auth_service
import app.services.database as database_service
import app.services.notebook as notebook_service
from app.services.authorization import is_admin, resolve_authorized_cyclist_and_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cyclists")


@router.get("/list")
async def get_cyclists_list(
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """List all available cyclists."""
    try:
        if is_admin(current_user):
            cyclists = database_service.get_all_cyclists_from_rides()
        else:
            cyclists = database_service.get_user_allowed_cyclists(
                str(current_user["id"])
            )
        return {
            "ok": True,
            "cyclists": cyclists,
            "n_cyclists": len(cyclists),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to list cyclists: {exc}"
        ) from exc
