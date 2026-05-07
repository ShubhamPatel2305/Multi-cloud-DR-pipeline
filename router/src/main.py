import random
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import Response

from src.canary import CanaryController, CanaryStep
from src.config import get_settings
from src.health_poller import HealthPoller
from src.pool import Origin, Pool

pool = Pool()
poller: HealthPoller | None = None
canary: CanaryController | None = None
client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global poller, canary, client

    s = get_settings()
    pool.upsert(Origin(name="aws-mumbai", url=s.origin_primary_url, priority=1))
    pool.upsert(Origin(name="aws-singapore", url=s.origin_standby_url, priority=2))
    pool.upsert(Origin(name="azure-secondary", url=s.origin_dr_url, priority=3))

    poller = HealthPoller(
        pool,
        poll_interval_s=s.poll_interval_seconds,
        deep_interval_s=s.deep_probe_interval_seconds,
        healthy_threshold=s.healthy_threshold,
        unhealthy_threshold=s.unhealthy_threshold,
    )
    await poller.start()

    canary = CanaryController(pool)
    client = httpx.AsyncClient(timeout=10.0)

    try:
        yield
    finally:
        await poller.stop()
        await client.aclose()


app = FastAPI(title="mock-cloudflare-router", version="0.1.0", lifespan=lifespan)


# ---------- Routing core ----------

def pick_origin() -> Origin | None:
    """
    Active-passive selection.

    Walk priorities ascending. At each priority, pick from healthy origins
    using their `weight` value as a probability — this is what lets the
    canary controller ramp a recovered region back into rotation.
    """
    healthy = pool.healthy()
    if not healthy:
        return None

    healthy.sort(key=lambda o: o.priority)
    top_priority = healthy[0].priority
    candidates = [o for o in healthy if o.priority == top_priority]

    total_weight = sum(o.weight for o in candidates)
    if total_weight == 0:
        # All weights zeroed (e.g. canary rolled back). Skip this tier.
        next_tier = [o for o in healthy if o.priority > top_priority]
        if not next_tier:
            return None
        return next_tier[0]

    pick = random.uniform(0, total_weight)
    cumulative = 0.0
    for origin in candidates:
        cumulative += origin.weight
        if pick <= cumulative:
            return origin
    return candidates[-1]


@app.api_route("/proxy/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request) -> Response:
    origin = pick_origin()
    if origin is None:
        raise HTTPException(status_code=503, detail="no healthy origin in pool")

    target_url = origin.url.rstrip("/") + "/" + path
    body = await request.body()

    fwd_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length"}
    }

    assert client is not None
    try:
        upstream = await client.request(
            request.method,
            target_url,
            params=request.query_params,
            content=body,
            headers=fwd_headers,
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"upstream error: {type(exc).__name__}")

    out_headers = dict(upstream.headers)
    out_headers["x-routed-to"] = origin.name
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=out_headers,
    )


# ---------- Admin / observability ----------

class CanaryStartRequest(BaseModel):
    target: str
    ramp: list[CanaryStep] | None = None


@app.get("/admin/pool")
async def get_pool():
    return {
        "origins": [
            {
                "name": o.name,
                "url": o.url,
                "priority": o.priority,
                "weight": o.weight,
                "state": o.state.value,
                "last_status_code": o.last_status_code,
                "last_probe_ms": o.last_probe_ms,
                "last_error": o.last_error,
                "consecutive_pass": o.consecutive_pass,
                "consecutive_fail": o.consecutive_fail,
            }
            for o in pool.snapshot()
        ]
    }


@app.post("/admin/canary/start")
async def start_canary(req: CanaryStartRequest):
    assert canary is not None
    try:
        run = canary.start(req.target)
        return {"started": True, "target": run.target}
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/admin/canary/abort")
async def abort_canary():
    assert canary is not None
    canary.abort()
    return {"aborted": True}


@app.get("/admin/canary/status")
async def canary_status():
    assert canary is not None
    if canary.status is None:
        return {"running": False}
    s = canary.status
    return {
        "running": canary.is_running(),
        "target": s.target,
        "current_step": s.current_step,
        "current_weight": s.current_weight,
        "state": s.state,
        "message": s.last_message,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
