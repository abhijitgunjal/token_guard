import time
import threading
import asyncio
from typing import Any, Dict, Optional, Tuple

from token_guard.policies.base import AsyncBasePolicy, BasePolicy
from token_guard.policies.models import PolicyContext, PolicyResult


class FixedWindowPolicy(BasePolicy):
    def __init__(self, limit: int, window: int = 3600, max_users: int = 10000) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if window <= 0:
            raise ValueError("window must be greater than 0")
        if max_users <= 0:
            raise ValueError("max_users must be greater than 0")
        self.limit = limit
        self.window = window
        self.max_users = max_users
        self._lock = threading.Lock()
        self._state: Dict[str, Tuple[float, int]] = {}  # user_id -> (window_start, count)

    def _evict_expired(self, now: float) -> None:
        if len(self._state) <= self.max_users:
            return
        expired = [uid for uid, (start, _) in self._state.items() if now - start >= self.window]
        for uid in expired:
            del self._state[uid]
        while len(self._state) > self.max_users:
            self._state.pop(next(iter(self._state)))

    def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        now = context.timestamp.timestamp()

        with self._lock:
            self._evict_expired(now)
            start, current_usage = self._state.get(context.user_id, (now, 0))
            if now - start >= self.window:
                start = now
                current_usage = 0

            if current_usage + context.total_tokens > self.limit:
                retry_after = round(self.window - (now - start), 2)
                return PolicyResult(
                    allowed=False,
                    reason=f"Fixed window token limit ({self.limit}) exceeded",
                    retry_after=max(0.0, retry_after),
                    metadata={"used": current_usage, "limit": self.limit, "window": self.window},
                )

            self._state[context.user_id] = (start, current_usage + context.total_tokens)
            return PolicyResult(
                allowed=True,
                metadata={"used": current_usage + context.total_tokens, "limit": self.limit, "window": self.window},
            )


class AsyncFixedWindowPolicy(AsyncBasePolicy):
    def __init__(self, limit: int, window: int = 3600, max_users: int = 10000) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if window <= 0:
            raise ValueError("window must be greater than 0")
        if max_users <= 0:
            raise ValueError("max_users must be greater than 0")
        self.limit = limit
        self.window = window
        self.max_users = max_users
        self._lock = asyncio.Lock()
        self._state: Dict[str, Tuple[float, int]] = {}

    def _evict_expired(self, now: float) -> None:
        if len(self._state) <= self.max_users:
            return
        expired = [uid for uid, (start, _) in self._state.items() if now - start >= self.window]
        for uid in expired:
            del self._state[uid]
        while len(self._state) > self.max_users:
            self._state.pop(next(iter(self._state)))

    async def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        now = context.timestamp.timestamp()

        async with self._lock:
            self._evict_expired(now)
            start, current_usage = self._state.get(context.user_id, (now, 0))
            if now - start >= self.window:
                start = now
                current_usage = 0

            if current_usage + context.total_tokens > self.limit:
                retry_after = round(self.window - (now - start), 2)
                return PolicyResult(
                    allowed=False,
                    reason=f"Fixed window token limit ({self.limit}) exceeded",
                    retry_after=max(0.0, retry_after),
                    metadata={"used": current_usage, "limit": self.limit, "window": self.window},
                )

            self._state[context.user_id] = (start, current_usage + context.total_tokens)
            return PolicyResult(
                allowed=True,
                metadata={"used": current_usage + context.total_tokens, "limit": self.limit, "window": self.window},
            )
