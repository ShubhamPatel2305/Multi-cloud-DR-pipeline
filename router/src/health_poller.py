import asyncio
import time

import httpx

from src.pool import Origin, OriginState, Pool


class HealthPoller:
    """
    Periodically probes /health/ready (cheap) and /health/deep (expensive)
    on every origin. State transitions are gated by N-consecutive thresholds
    to avoid flapping on a single bad packet.
    """

    def __init__(
        self,
        pool: Pool,
        *,
        poll_interval_s: float,
        deep_interval_s: float,
        healthy_threshold: int,
        unhealthy_threshold: int,
    ) -> None:
        self.pool = pool
        self.poll_interval_s = poll_interval_s
        self.deep_interval_s = deep_interval_s
        self.healthy_threshold = healthy_threshold
        self.unhealthy_threshold = unhealthy_threshold
        self._task: asyncio.Task | None = None
        self._deep_task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=2.0)
        self._task = asyncio.create_task(self._run_loop("/health/ready", self.poll_interval_s))
        self._deep_task = asyncio.create_task(self._run_loop("/health/deep", self.deep_interval_s))

    async def stop(self) -> None:
        for t in (self._task, self._deep_task):
            if t:
                t.cancel()
        if self._client:
            await self._client.aclose()

    async def _run_loop(self, path: str, interval_s: float) -> None:
        assert self._client is not None
        while True:
            try:
                await asyncio.gather(
                    *(self._probe(o, path) for o in self.pool.snapshot()),
                    return_exceptions=True,
                )
            except Exception:
                pass
            await asyncio.sleep(interval_s)

    async def _probe(self, origin: Origin, path: str) -> None:
        assert self._client is not None
        url = origin.url.rstrip("/") + path
        started = time.perf_counter()
        try:
            r = await self._client.get(url)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            origin.last_probe_ms = round(elapsed_ms, 2)
            origin.last_status_code = r.status_code
            origin.last_error = None

            if 200 <= r.status_code < 300:
                self._record_pass(origin)
            else:
                self._record_fail(origin, f"http_{r.status_code}")
        except Exception as exc:
            origin.last_error = type(exc).__name__
            origin.last_status_code = None
            self._record_fail(origin, type(exc).__name__)

    def _record_pass(self, origin: Origin) -> None:
        origin.consecutive_pass += 1
        origin.consecutive_fail = 0
        if (
            origin.state is not OriginState.HEALTHY
            and origin.consecutive_pass >= self.healthy_threshold
        ):
            origin.state = OriginState.HEALTHY

    def _record_fail(self, origin: Origin, _reason: str) -> None:
        origin.consecutive_fail += 1
        origin.consecutive_pass = 0
        if (
            origin.state is OriginState.HEALTHY
            and origin.consecutive_fail >= self.unhealthy_threshold
        ):
            origin.state = OriginState.UNHEALTHY
