import asyncio
import time
from dataclasses import dataclass

from src.pool import Origin, OriginState, Pool


@dataclass
class CanaryStep:
    weight_pct: int
    hold_seconds: int


DEFAULT_RAMP: list[CanaryStep] = [
    CanaryStep(weight_pct=5, hold_seconds=120),
    CanaryStep(weight_pct=25, hold_seconds=180),
    CanaryStep(weight_pct=50, hold_seconds=180),
    CanaryStep(weight_pct=100, hold_seconds=0),
]


@dataclass
class CanaryRun:
    target: str
    started_at: float
    current_step: int = 0
    current_weight: int = 0
    state: str = "running"   # running | rolled_back | completed
    last_message: str = ""


class CanaryController:
    """
    Stepped failback controller.

    A canary run is started against ONE origin (the recovered primary).
    On each step, the target's weight is raised, held for `hold_seconds`,
    and re-evaluated. If the origin transitions away from HEALTHY during
    the hold window, weight is rolled back to 0 and the run is aborted.
    """

    def __init__(self, pool: Pool, ramp: list[CanaryStep] | None = None) -> None:
        self.pool = pool
        self.ramp = ramp or DEFAULT_RAMP
        self._task: asyncio.Task | None = None
        self._run: CanaryRun | None = None

    @property
    def status(self) -> CanaryRun | None:
        return self._run

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, target_name: str) -> CanaryRun:
        if self.is_running():
            raise RuntimeError("a canary run is already in progress")

        target = self.pool.get(target_name)
        if target is None:
            raise ValueError(f"unknown origin: {target_name}")
        if target.state is not OriginState.HEALTHY:
            raise RuntimeError(
                f"refusing to start canary on {target_name}: state={target.state.value}"
            )

        self._run = CanaryRun(target=target_name, started_at=time.time())
        self.pool.set_weight(target_name, 0)
        self._task = asyncio.create_task(self._drive(target))
        return self._run

    def abort(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        if self._run is not None:
            self._run.state = "rolled_back"
            self._run.last_message = "manually aborted"
            self.pool.set_weight(self._run.target, 0)

    async def _drive(self, target: Origin) -> None:
        assert self._run is not None
        try:
            for i, step in enumerate(self.ramp):
                self._run.current_step = i
                self._run.current_weight = step.weight_pct
                self.pool.set_weight(target.name, step.weight_pct)
                self._run.last_message = f"raised {target.name} to {step.weight_pct}%"

                if step.hold_seconds == 0:
                    continue

                if not await self._hold_and_verify(target, step.hold_seconds):
                    self._run.state = "rolled_back"
                    self.pool.set_weight(target.name, 0)
                    self._run.last_message = (
                        f"degraded during {step.weight_pct}% step; rolled back"
                    )
                    return

            self._run.state = "completed"
            self._run.last_message = "ramp completed at 100%"
        except asyncio.CancelledError:
            return

    async def _hold_and_verify(self, target: Origin, hold_seconds: int) -> bool:
        """Wait `hold_seconds` and verify the origin stayed HEALTHY throughout."""
        deadline = time.time() + hold_seconds
        while time.time() < deadline:
            current = self.pool.get(target.name)
            if current is None or current.state is not OriginState.HEALTHY:
                return False
            await asyncio.sleep(1.0)
        return True
