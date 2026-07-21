import asyncio
import threading
from typing import Any, Dict, List, Optional, Tuple

from token_guard.policies.base import AsyncBasePolicy, BasePolicy
from token_guard.policies.models import PolicyContext, PolicyResult


class SlidingWindowPolicy(BasePolicy):
    def __init__(self, limit: int, window: int = 3600, buckets: int = 60) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if window <= 0:
            raise ValueError("window must be greater than 0")
        if buckets <= 0:
            raise ValueError("buckets must be greater than 0")

        self.limit = limit
        self.window = window
        self.buckets = buckets
        self.bucket_duration = window / buckets
        self._lock = threading.Lock()
        # user_id -> list of (bucket_timestamp, token_count)
        self._state: Dict[str, List[Tuple[float, int]]] = {}

    def _clean_and_sum(self, user_id: str, now: float) -> Tuple[List[Tuple[float, int]], int]:
        cutoff = now - self.window
        user_buckets = self._state.get(user_id, [])
        active_buckets = [(ts, count) for ts, count in user_buckets if ts > cutoff]
        total_tokens = sum(count for _, count in active_buckets)
        return active_buckets, total_tokens

    def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        now = context.timestamp.timestamp()

        with self._lock:
            active_buckets, current_usage = self._clean_and_sum(context.user_id, now)

            if current_usage + context.total_tokens > self.limit:
                oldest_ts = active_buckets[0][0] if active_buckets else now
                retry_after = round(oldest_ts + self.window - now, 2)
                return PolicyResult(
                    allowed=False,
                    reason=f"Sliding window token limit ({self.limit}) exceeded",
                    retry_after=max(0.1, retry_after),
                    metadata={"used": current_usage, "limit": self.limit, "window": self.window},
                )

            current_bucket_ts = now - (now % self.bucket_duration)
            if active_buckets and active_buckets[-1][0] == current_bucket_ts:
                active_buckets[-1] = (current_bucket_ts, active_buckets[-1][1] + context.total_tokens)
            else:
                active_buckets.append((current_bucket_ts, context.total_tokens))

            self._state[context.user_id] = active_buckets
            return PolicyResult(
                allowed=True,
                metadata={"used": current_usage + context.total_tokens, "limit": self.limit, "window": self.window},
            )


class AsyncSlidingWindowPolicy(AsyncBasePolicy):
    def __init__(self, limit: int, window: int = 3600, buckets: int = 60) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if window <= 0:
            raise ValueError("window must be greater than 0")
        if buckets <= 0:
            raise ValueError("buckets must be greater than 0")

        self.limit = limit
        self.window = window
        self.buckets = buckets
        self.bucket_duration = window / buckets
        self._lock = asyncio.Lock()
        self._state: Dict[str, List[Tuple[float, int]]] = {}

    def _clean_and_sum(self, user_id: str, now: float) -> Tuple[List[Tuple[float, int]], int]:
        cutoff = now - self.window
        user_buckets = self._state.get(user_id, [])
        active_buckets = [(ts, count) for ts, count in user_buckets if ts > cutoff]
        total_tokens = sum(count for _, count in active_buckets)
        return active_buckets, total_tokens

    async def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        now = context.timestamp.timestamp()

        async with self._lock:
            active_buckets, current_usage = self._clean_and_sum(context.user_id, now)

            if current_usage + context.total_tokens > self.limit:
                oldest_ts = active_buckets[0][0] if active_buckets else now
                retry_after = round(oldest_ts + self.window - now, 2)
                return PolicyResult(
                    allowed=False,
                    reason=f"Sliding window token limit ({self.limit}) exceeded",
                    retry_after=max(0.1, retry_after),
                    metadata={"used": current_usage, "limit": self.limit, "window": self.window},
                )

            current_bucket_ts = now - (now % self.bucket_duration)
            if active_buckets and active_buckets[-1][0] == current_bucket_ts:
                active_buckets[-1] = (current_bucket_ts, active_buckets[-1][1] + context.total_tokens)
            else:
                active_buckets.append((current_bucket_ts, context.total_tokens))

            self._state[context.user_id] = active_buckets
            return PolicyResult(
                allowed=True,
                metadata={"used": current_usage + context.total_tokens, "limit": self.limit, "window": self.window},
            )
