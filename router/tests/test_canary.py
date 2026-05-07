import asyncio

import pytest

from src.canary import CanaryController, CanaryStep
from src.pool import Origin, OriginState, Pool


@pytest.fixture
def pool():
    p = Pool()
    p.upsert(Origin(name="primary", url="http://x", priority=1, state=OriginState.HEALTHY))
    return p


@pytest.mark.asyncio
async def test_start_rejects_unhealthy_target(pool: Pool):
    pool.get("primary").state = OriginState.UNHEALTHY
    c = CanaryController(pool)
    with pytest.raises(RuntimeError):
        c.start("primary")


@pytest.mark.asyncio
async def test_start_rejects_unknown_target(pool: Pool):
    c = CanaryController(pool)
    with pytest.raises(ValueError):
        c.start("does-not-exist")


@pytest.mark.asyncio
async def test_canary_completes_when_target_stays_healthy(pool: Pool):
    fast_ramp = [
        CanaryStep(weight_pct=5, hold_seconds=1),
        CanaryStep(weight_pct=25, hold_seconds=1),
        CanaryStep(weight_pct=100, hold_seconds=0),
    ]
    c = CanaryController(pool, ramp=fast_ramp)
    c.start("primary")
    await asyncio.sleep(3.5)

    assert c.status is not None
    assert c.status.state == "completed"
    assert pool.get("primary").weight == 100


@pytest.mark.asyncio
async def test_canary_rolls_back_on_state_flip(pool: Pool):
    fast_ramp = [
        CanaryStep(weight_pct=5, hold_seconds=2),
        CanaryStep(weight_pct=100, hold_seconds=0),
    ]
    c = CanaryController(pool, ramp=fast_ramp)
    c.start("primary")
    await asyncio.sleep(0.3)

    pool.get("primary").state = OriginState.UNHEALTHY
    await asyncio.sleep(2.0)

    assert c.status.state == "rolled_back"
    assert pool.get("primary").weight == 0
