import time
from typing import Any

from fastapi import APIRouter, Response, status

from src.config import get_settings
from src.db import ping as db_ping
from src.utils.logging import get_logger

router = APIRouter(prefix="/health", tags=["health"])
log = get_logger("health")

_started_at = time.time()


@router.get("/live")
async def live() -> dict[str, Any]:
    """Process is up. No dependency checks. Used by container orchestrator."""
    settings = get_settings()
    return {
        "status": "live",
        "region": settings.region_id,
        "uptime_s": round(time.time() - _started_at, 2),
    }


@router.get("/ready")
async def ready(response: Response) -> dict[str, Any]:
    """
    Region is ready to receive traffic.
    Used by Cloudflare / mock router for pool membership decisions.
    """
    settings = get_settings()

    if settings.inject_failure and settings.failure_mode in {"ready", "all"}:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "region": settings.region_id, "reason": "injected"}

    db_ok = await db_ping(timeout=1.0)
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "region": settings.region_id, "reason": "db_unreachable"}

    return {"status": "ready", "region": settings.region_id}


@router.get("/deep")
async def deep(response: Response) -> dict[str, Any]:
    """
    Deep health: every dependency this region needs to serve real traffic.
    More expensive; polled at a slower cadence than /ready.
    """
    settings = get_settings()
    checks: dict[str, str] = {}

    if settings.inject_failure and settings.failure_mode in {"deep", "all"}:
        checks["injected_failure"] = "fail"

    db_ok = await db_ping(timeout=1.5)
    checks["mongo"] = "ok" if db_ok else "fail"

    # Placeholders for additional dependencies a real region would check.
    # In TTFA's production we also probed object storage, payment gateway, and the
    # CDN origin endpoint here.
    checks["object_storage"] = "ok"
    checks["payment_gateway"] = "ok"

    overall_ok = all(v == "ok" for v in checks.values())
    if not overall_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "healthy" if overall_ok else "degraded",
        "region": settings.region_id,
        "priority": settings.region_priority,
        "checks": checks,
    }
