import asyncio
import threading
from typing import Any, Dict, Optional, Tuple

from token_guard.policies.base import AsyncBasePolicy, BasePolicy
from token_guard.policies.models import PolicyContext, PolicyResult


class TokenBucketPolicy(BasePolicy):
    def __init__(self, capacity: int, refill_rate: float) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be greater than 0")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be greater than 0")

        self.capacity = capacity
        self.refill_rate = refill_rate
        self._lock = threading.Lock()
        # user_id -> (last_update_ts, current_tokens)
        self._state: Dict[str, Tuple[float, float]] = {}

    def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        now = context.timestamp.timestamp()

        with self._lock:
            last_ts, current_tokens = self._state.get(context.user_id, (now, float(self.capacity)))
            elapsed = max(0.0, now - last_ts)
            refilled_tokens = min(float(self.capacity), current_tokens + (elapsed * self.refill_rate))

            needed = float(context.total_tokens)
            if refilled_tokens < needed:
                deficit = needed - refilled_tokens
                retry_after = round(deficit / self.refill_rate, 2)
                return PolicyResult(
                    allowed=False,
                    reason=f"Token bucket capacity insufficient ({int(refilled_tokens)} available, {int(needed)} required)",
                    retry_after=max(0.1, retry_after),
                    metadata={"available": refilled_tokens, "capacity": self.capacity},
                )

            remaining = refilled_tokens - needed
            self._state[context.user_id] = (now, remaining)
            return PolicyResult(
                allowed=True,
                metadata={"available": remaining, "capacity": self.capacity},
            )


class AsyncTokenBucketPolicy(AsyncBasePolicy):
    def __init__(self, capacity: int, refill_rate: float) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be greater than 0")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be greater than 0")

        self.capacity = capacity
        self.refill_rate = refill_rate
        self._lock = asyncio.Lock()
        self._state: Dict[str, Tuple[float, float]] = {}

    async def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        now = context.timestamp.timestamp()

        async with self._lock:
            last_ts, current_tokens = self._state.get(context.user_id, (now, float(self.capacity)))
            elapsed = max(0.0, now - last_ts)
            refilled_tokens = min(float(self.capacity), current_tokens + (elapsed * self.refill_rate))

            needed = float(context.total_tokens)
            if refilled_tokens < needed:
                deficit = needed - refilled_tokens
                retry_after = round(deficit / self.refill_rate, 2)
                return PolicyResult(
                    allowed=False,
                    reason=f"Token bucket capacity insufficient ({int(refilled_tokens)} available, {int(needed)} required)",
                    retry_after=max(0.1, retry_after),
                    metadata={"available": refilled_tokens, "capacity": self.capacity},
                )

            remaining = refilled_tokens - needed
            self._state[context.user_id] = (now, remaining)
            return PolicyResult(
                allowed=True,
                metadata={"available": remaining, "capacity": self.capacity},
            )
