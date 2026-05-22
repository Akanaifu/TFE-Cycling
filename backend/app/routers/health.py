from fastapi import APIRouter, Response, status
import logging

from app.services import database as database_service

router = APIRouter(prefix="/health", tags=["ops"])
logger = logging.getLogger(__name__)


@router.get("", include_in_schema=False)
def health_check(response: Response):
    checks = {}
    healthy = True

    try:
        db_status = database_service.get_database_status()
        checks["database"] = db_status
        if not db_status.get("connected"):
            healthy = False
    except Exception as exc:
        checks["database"] = {"connected": False, "error": str(exc)}
        healthy = False
        logger.exception("health_check.database_failure")

    checks["uptime_seconds"] = "unknown"

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning("health_check.unhealthy", extra={"checks": checks})
        return {"status": "unhealthy", "checks": checks}

    logger.info("health_check.ok", extra={"checks": checks})
    return {"status": "healthy", "checks": checks}
