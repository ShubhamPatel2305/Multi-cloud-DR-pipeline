from dataclasses import dataclass, field
from enum import Enum
from threading import RLock


class OriginState(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DRAINING = "draining"


@dataclass
class Origin:
    name: str
    url: str
    priority: int
    weight: int = 100
    state: OriginState = OriginState.UNHEALTHY
    consecutive_pass: int = 0
    consecutive_fail: int = 0
    last_probe_ms: float | None = None
    last_status_code: int | None = None
    last_error: str | None = None


@dataclass
class Pool:
    """
    Active-passive pool. Origins are sorted by priority — lower number wins.
    Weight controls intra-priority traffic split, used during canary failback
    to ramp the recovered region back into rotation.
    """

    origins: list[Origin] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock)

    def upsert(self, origin: Origin) -> None:
        with self._lock:
            for i, o in enumerate(self.origins):
                if o.name == origin.name:
                    self.origins[i] = origin
                    return
            self.origins.append(origin)
            self.origins.sort(key=lambda o: o.priority)

    def get(self, name: str) -> Origin | None:
        with self._lock:
            for o in self.origins:
                if o.name == name:
                    return o
        return None

    def healthy(self) -> list[Origin]:
        with self._lock:
            return [o for o in self.origins if o.state is OriginState.HEALTHY]

    def snapshot(self) -> list[Origin]:
        with self._lock:
            return list(self.origins)

    def set_weight(self, name: str, weight: int) -> bool:
        with self._lock:
            o = self.get(name)
            if o is None:
                return False
            o.weight = max(0, min(100, weight))
            return True
