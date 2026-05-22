import logging
import os
import httpx

logger = logging.getLogger("alerts")
WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")


async def send_alert(title: str, message: str, level: str = "warning") -> None:
    if not WEBHOOK_URL:
        logger.debug("send_alert: ALERT_WEBHOOK_URL not configured, skipping")
        return

    emoji = {"critical": "🔴", "warning": "🟡", "info": "🟢"}.get(level, "⚪")
    payload = {"text": f"{emoji} *{title}*\n{message}"}

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(WEBHOOK_URL, json=payload)
            resp.raise_for_status()
    except Exception as exc:
        logger.error("send_alert.failed", extra={"error": str(exc)})
