import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

from src import db
from src.config import get_settings
from src.health import router as health_router
from src.routes.admin import router as admin_router
from src.routes.courses import router as courses_router
from src.utils.logging import configure_logging, get_logger

REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests handled by this region.",
    ["method", "path", "status", "region"],
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "Request latency by route.",
    ["method", "path", "region"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level, settings.region_id)
    log = get_logger("startup")

    log.info(
        "starting",
        env=settings.app_env,
        region=settings.region_id,
        priority=settings.region_priority,
    )

    await db.connect(settings)
    try:
        yield
    finally:
        await db.disconnect()
        log.info("stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env != "prod" else None,
        redoc_url=None,
    )

    app.include_router(health_router)
    app.include_router(courses_router)
    app.include_router(admin_router)

    @app.get("/", tags=["meta"])
    async def root():
        return {
            "service": settings.app_name,
            "region": settings.region_id,
            "priority": settings.region_priority,
        }

    @app.get("/metrics", tags=["meta"])
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.middleware("http")
    async def observe(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started

        path = request.scope.get("route").path if request.scope.get("route") else request.url.path
        labels = {"method": request.method, "path": path, "region": settings.region_id}

        REQUESTS.labels(**labels, status=str(response.status_code)).inc()
        LATENCY.labels(**labels).observe(elapsed)

        response.headers["x-served-by"] = settings.region_id
        return response

    return app


app = create_app()
