import asyncio
import threading
from typing import Any, Dict, Optional

from token_guard.policies.base import AsyncBasePolicy, BasePolicy
from token_guard.policies.models import PolicyContext, PolicyResult


class CostPolicy(BasePolicy):
    def __init__(
        self,
        daily_limit_usd: Optional[float] = None,
        monthly_limit_usd: Optional[float] = None,
        cost_per_1k_input_tokens: float = 0.0015,
        cost_per_1k_output_tokens: float = 0.002,
    ) -> None:
        if daily_limit_usd is not None and daily_limit_usd <= 0:
            raise ValueError("daily_limit_usd must be positive")
        if monthly_limit_usd is not None and monthly_limit_usd <= 0:
            raise ValueError("monthly_limit_usd must be positive")

        self.daily_limit_usd = daily_limit_usd
        self.monthly_limit_usd = monthly_limit_usd
        self.cost_input = cost_per_1k_input_tokens
        self.cost_output = cost_per_1k_output_tokens
        self._lock = threading.Lock()
        # user_id -> {"day": day_str, "daily_cost": float, "month": month_str, "monthly_cost": float}
        self._state: Dict[str, Dict[str, Any]] = {}

    def _estimate_cost(self, context: PolicyContext) -> float:
        input_cost = (context.input_tokens / 1000.0) * self.cost_input
        output_cost = (context.output_tokens / 1000.0) * self.cost_output
        if input_cost == 0 and output_cost == 0 and context.total_tokens > 0:
            return (context.total_tokens / 1000.0) * self.cost_input
        return input_cost + output_cost

    def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        dt = context.timestamp
        day_str = dt.strftime("%Y-%m-%d")
        month_str = dt.strftime("%Y-%m")
        estimated_cost = self._estimate_cost(context)

        with self._lock:
            user_data = self._state.get(context.user_id, {
                "day": day_str, "daily_cost": 0.0,
                "month": month_str, "monthly_cost": 0.0
            })

            daily_cost = user_data["daily_cost"] if user_data["day"] == day_str else 0.0
            monthly_cost = user_data["monthly_cost"] if user_data["month"] == month_str else 0.0

            if self.daily_limit_usd is not None and (daily_cost + estimated_cost) > self.daily_limit_usd:
                return PolicyResult(
                    allowed=False,
                    reason=f"Daily cost limit (${self.daily_limit_usd:.2f}) exceeded",
                    metadata={"daily_cost": round(daily_cost, 4), "request_cost": round(estimated_cost, 4)},
                )

            if self.monthly_limit_usd is not None and (monthly_cost + estimated_cost) > self.monthly_limit_usd:
                return PolicyResult(
                    allowed=False,
                    reason=f"Monthly cost limit (${self.monthly_limit_usd:.2f}) exceeded",
                    metadata={"monthly_cost": round(monthly_cost, 4), "request_cost": round(estimated_cost, 4)},
                )

            self._state[context.user_id] = {
                "day": day_str,
                "daily_cost": daily_cost + estimated_cost,
                "month": month_str,
                "monthly_cost": monthly_cost + estimated_cost,
            }
            return PolicyResult(
                allowed=True,
                metadata={"request_cost": round(estimated_cost, 4)},
            )


class AsyncCostPolicy(AsyncBasePolicy):
    def __init__(
        self,
        daily_limit_usd: Optional[float] = None,
        monthly_limit_usd: Optional[float] = None,
        cost_per_1k_input_tokens: float = 0.0015,
        cost_per_1k_output_tokens: float = 0.002,
    ) -> None:
        if daily_limit_usd is not None and daily_limit_usd <= 0:
            raise ValueError("daily_limit_usd must be positive")
        if monthly_limit_usd is not None and monthly_limit_usd <= 0:
            raise ValueError("monthly_limit_usd must be positive")

        self.daily_limit_usd = daily_limit_usd
        self.monthly_limit_usd = monthly_limit_usd
        self.cost_input = cost_per_1k_input_tokens
        self.cost_output = cost_per_1k_output_tokens
        self._lock = asyncio.Lock()
        self._state: Dict[str, Dict[str, Any]] = {}

    def _estimate_cost(self, context: PolicyContext) -> float:
        input_cost = (context.input_tokens / 1000.0) * self.cost_input
        output_cost = (context.output_tokens / 1000.0) * self.cost_output
        if input_cost == 0 and output_cost == 0 and context.total_tokens > 0:
            return (context.total_tokens / 1000.0) * self.cost_input
        return input_cost + output_cost

    async def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        dt = context.timestamp
        day_str = dt.strftime("%Y-%m-%d")
        month_str = dt.strftime("%Y-%m")
        estimated_cost = self._estimate_cost(context)

        async with self._lock:
            user_data = self._state.get(context.user_id, {
                "day": day_str, "daily_cost": 0.0,
                "month": month_str, "monthly_cost": 0.0
            })

            daily_cost = user_data["daily_cost"] if user_data["day"] == day_str else 0.0
            monthly_cost = user_data["monthly_cost"] if user_data["month"] == month_str else 0.0

            if self.daily_limit_usd is not None and (daily_cost + estimated_cost) > self.daily_limit_usd:
                return PolicyResult(
                    allowed=False,
                    reason=f"Daily cost limit (${self.daily_limit_usd:.2f}) exceeded",
                    metadata={"daily_cost": round(daily_cost, 4), "request_cost": round(estimated_cost, 4)},
                )

            if self.monthly_limit_usd is not None and (monthly_cost + estimated_cost) > self.monthly_limit_usd:
                return PolicyResult(
                    allowed=False,
                    reason=f"Monthly cost limit (${self.monthly_limit_usd:.2f}) exceeded",
                    metadata={"monthly_cost": round(monthly_cost, 4), "request_cost": round(estimated_cost, 4)},
                )

            self._state[context.user_id] = {
                "day": day_str,
                "daily_cost": daily_cost + estimated_cost,
                "month": month_str,
                "monthly_cost": monthly_cost + estimated_cost,
            }
            return PolicyResult(
                allowed=True,
                metadata={"request_cost": round(estimated_cost, 4)},
            )
