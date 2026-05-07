from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.config import get_settings

router = APIRouter(prefix="/admin", tags=["admin"])


class FailureSpec(BaseModel):
    mode: Literal["none", "ready", "deep", "all"]


@router.post("/inject-failure", status_code=status.HTTP_202_ACCEPTED)
async def inject_failure(spec: FailureSpec):
    """
    Toggle synthetic failure for chaos / runbook drills.
    Production deployments would gate this behind auth + a feature flag.
    """
    if get_settings().app_env == "prod":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "disabled in prod")

    settings = get_settings()
    settings.failure_mode = spec.mode
    settings.inject_failure = spec.mode != "none"
    return {"injected": settings.inject_failure, "mode": settings.failure_mode}


@router.get("/state")
async def state():
    s = get_settings()
    return {
        "region": s.region_id,
        "priority": s.region_priority,
        "inject_failure": s.inject_failure,
        "failure_mode": s.failure_mode,
        "env": s.app_env,
    }
