import asyncio
import threading
from typing import Any, Dict, Optional, Tuple

from token_guard.policies.base import AsyncBasePolicy, BasePolicy
from token_guard.policies.models import PolicyContext, PolicyResult


class LeakyBucketPolicy(BasePolicy):
    def __init__(self, capacity: int, leak_rate: float) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be greater than 0")
        if leak_rate <= 0:
            raise ValueError("leak_rate must be greater than 0")

        self.capacity = capacity
        self.leak_rate = leak_rate
        self._lock = threading.Lock()
        # user_id -> (last_leak_ts, current_volume)
        self._state: Dict[str, Tuple[float, float]] = {}

    def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        now = context.timestamp.timestamp()

        with self._lock:
            last_ts, current_volume = self._state.get(context.user_id, (now, 0.0))
            elapsed = max(0.0, now - last_ts)
            leaked_volume = max(0.0, current_volume - (elapsed * self.leak_rate))

            needed = float(context.total_tokens)
            if leaked_volume + needed > self.capacity:
                excess = (leaked_volume + needed) - self.capacity
                retry_after = round(excess / self.leak_rate, 2)
                return PolicyResult(
                    allowed=False,
                    reason=f"Leaky bucket capacity ({self.capacity}) overflow",
                    retry_after=max(0.1, retry_after),
                    metadata={"current_volume": leaked_volume, "capacity": self.capacity},
                )

            new_volume = leaked_volume + needed
            self._state[context.user_id] = (now, new_volume)
            return PolicyResult(
                allowed=True,
                metadata={"current_volume": new_volume, "capacity": self.capacity},
            )


class AsyncLeakyBucketPolicy(AsyncBasePolicy):
    def __init__(self, capacity: int, leak_rate: float) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be greater than 0")
        if leak_rate <= 0:
            raise ValueError("leak_rate must be greater than 0")

        self.capacity = capacity
        self.leak_rate = leak_rate
        self._lock = asyncio.Lock()
        self._state: Dict[str, Tuple[float, float]] = {}

    async def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        now = context.timestamp.timestamp()

        async with self._lock:
            last_ts, current_volume = self._state.get(context.user_id, (now, 0.0))
            elapsed = max(0.0, now - last_ts)
            leaked_volume = max(0.0, current_volume - (elapsed * self.leak_rate))

            needed = float(context.total_tokens)
            if leaked_volume + needed > self.capacity:
                excess = (leaked_volume + needed) - self.capacity
                retry_after = round(excess / self.leak_rate, 2)
                return PolicyResult(
                    allowed=False,
                    reason=f"Leaky bucket capacity ({self.capacity}) overflow",
                    retry_after=max(0.1, retry_after),
                    metadata={"current_volume": leaked_volume, "capacity": self.capacity},
                )

            new_volume = leaked_volume + needed
            self._state[context.user_id] = (now, new_volume)
            return PolicyResult(
                allowed=True,
                metadata={"current_volume": new_volume, "capacity": self.capacity},
            )
