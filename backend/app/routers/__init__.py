"""API routers for TFE Cycling backend."""

from fastapi import APIRouter
from . import auth, strava, cyclists, rides, analysis, diagnostic, health

# Create main router to include all sub-routers
router = APIRouter()

router.include_router(auth.router, tags=["auth"])
router.include_router(strava.router, tags=["strava"])
router.include_router(cyclists.router, tags=["cyclists"])
router.include_router(rides.router, tags=["rides"])
router.include_router(analysis.router, tags=["analysis"])
router.include_router(diagnostic.router, tags=["diagnostic"])
router.include_router(health.router, tags=["ops"])

__all__ = ["router"]
