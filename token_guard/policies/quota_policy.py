import asyncio
import threading
from typing import Any, Dict, Optional

from token_guard.policies.base import AsyncBasePolicy, BasePolicy
from token_guard.policies.models import PolicyContext, PolicyResult


class QuotaPolicy(BasePolicy):
    def __init__(
        self,
        daily_tokens: Optional[int] = None,
        monthly_tokens: Optional[int] = None,
    ) -> None:
        if daily_tokens is not None and daily_tokens <= 0:
            raise ValueError("daily_tokens must be positive")
        if monthly_tokens is not None and monthly_tokens <= 0:
            raise ValueError("monthly_tokens must be positive")

        self.daily_tokens = daily_tokens
        self.monthly_tokens = monthly_tokens
        self._lock = threading.Lock()
        # user_id -> {"day": str, "daily_used": int, "month": str, "monthly_used": int}
        self._state: Dict[str, Dict[str, Any]] = {}

    def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        dt = context.timestamp
        day_str = dt.strftime("%Y-%m-%d")
        month_str = dt.strftime("%Y-%m")

        with self._lock:
            user_data = self._state.get(context.user_id, {
                "day": day_str, "daily_used": 0,
                "month": month_str, "monthly_used": 0
            })

            daily_used = user_data["daily_used"] if user_data["day"] == day_str else 0
            monthly_used = user_data["monthly_used"] if user_data["month"] == month_str else 0

            if self.daily_tokens is not None and (daily_used + context.total_tokens) > self.daily_tokens:
                return PolicyResult(
                    allowed=False,
                    reason=f"Daily token quota ({self.daily_tokens:,}) exceeded",
                    metadata={"daily_used": daily_used, "limit": self.daily_tokens},
                )

            if self.monthly_tokens is not None and (monthly_used + context.total_tokens) > self.monthly_tokens:
                return PolicyResult(
                    allowed=False,
                    reason=f"Monthly token quota ({self.monthly_tokens:,}) exceeded",
                    metadata={"monthly_used": monthly_used, "limit": self.monthly_tokens},
                )

            self._state[context.user_id] = {
                "day": day_str,
                "daily_used": daily_used + context.total_tokens,
                "month": month_str,
                "monthly_used": monthly_used + context.total_tokens,
            }
            return PolicyResult(
                allowed=True,
                metadata={"daily_used": daily_used + context.total_tokens},
            )


class AsyncQuotaPolicy(AsyncBasePolicy):
    def __init__(
        self,
        daily_tokens: Optional[int] = None,
        monthly_tokens: Optional[int] = None,
    ) -> None:
        if daily_tokens is not None and daily_tokens <= 0:
            raise ValueError("daily_tokens must be positive")
        if monthly_tokens is not None and monthly_tokens <= 0:
            raise ValueError("monthly_tokens must be positive")

        self.daily_tokens = daily_tokens
        self.monthly_tokens = monthly_tokens
        self._lock = asyncio.Lock()
        self._state: Dict[str, Dict[str, Any]] = {}

    async def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        dt = context.timestamp
        day_str = dt.strftime("%Y-%m-%d")
        month_str = dt.strftime("%Y-%m")

        async with self._lock:
            user_data = self._state.get(context.user_id, {
                "day": day_str, "daily_used": 0,
                "month": month_str, "monthly_used": 0
            })

            daily_used = user_data["daily_used"] if user_data["day"] == day_str else 0
            monthly_used = user_data["monthly_used"] if user_data["month"] == month_str else 0

            if self.daily_tokens is not None and (daily_used + context.total_tokens) > self.daily_tokens:
                return PolicyResult(
                    allowed=False,
                    reason=f"Daily token quota ({self.daily_tokens:,}) exceeded",
                    metadata={"daily_used": daily_used, "limit": self.daily_tokens},
                )

            if self.monthly_tokens is not None and (monthly_used + context.total_tokens) > self.monthly_tokens:
                return PolicyResult(
                    allowed=False,
                    reason=f"Monthly token quota ({self.monthly_tokens:,}) exceeded",
                    metadata={"monthly_used": monthly_used, "limit": self.monthly_tokens},
                )

            self._state[context.user_id] = {
                "day": day_str,
                "daily_used": daily_used + context.total_tokens,
                "month": month_str,
                "monthly_used": monthly_used + context.total_tokens,
            }
            return PolicyResult(
                allowed=True,
                metadata={"daily_used": daily_used + context.total_tokens},
            )
