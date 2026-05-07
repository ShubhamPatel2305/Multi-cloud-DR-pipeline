import pytest
from httpx import ASGITransport, AsyncClient

from src.config import get_settings
from src.main import app


@pytest.fixture(autouse=True)
def reset_failure_flag():
    s = get_settings()
    s.inject_failure = False
    s.failure_mode = "none"
    yield
    s.inject_failure = False
    s.failure_mode = "none"


@pytest.mark.asyncio
async def test_live_always_returns_200():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "live"


@pytest.mark.asyncio
async def test_inject_failure_flips_ready_to_503():
    s = get_settings()
    s.inject_failure = True
    s.failure_mode = "ready"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/health/ready")
        assert r.status_code == 503
        assert r.json()["reason"] == "injected"
