import asyncio
import threading
from typing import Any, Dict, Optional, Union

from token_guard.policies.base import AsyncBasePolicy, BasePolicy
from token_guard.policies.models import PolicyContext, PolicyResult


class RolePolicy(BasePolicy):
    def __init__(
        self,
        role_limits: Optional[Dict[str, Union[int, float]]] = None,
        user_roles: Optional[Dict[str, str]] = None,
        default_role: str = "guest",
        default_limit: Union[int, float] = 50_000,
    ) -> None:
        self.role_limits = role_limits or {
            "admin": float("inf"),
            "developer": 1_000_000,
            "guest": 50_000,
        }
        self.user_roles = user_roles or {}
        self.default_role = default_role
        self.default_limit = default_limit
        self._lock = threading.Lock()
        self._state: Dict[str, int] = {}  # user_id -> cumulative_used

    def get_role(self, context: PolicyContext) -> str:
        if "role" in context.metadata:
            return str(context.metadata["role"])
        return self.user_roles.get(context.user_id, self.default_role)

    def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        role = self.get_role(context)
        limit = self.role_limits.get(role, self.default_limit)

        with self._lock:
            current_used = self._state.get(context.user_id, 0)
            if limit != float("inf") and current_used + context.total_tokens > limit:
                return PolicyResult(
                    allowed=False,
                    reason=f"Role '{role}' token limit ({int(limit):,}) exceeded",
                    metadata={"role": role, "used": current_used, "limit": limit},
                )

            self._state[context.user_id] = current_used + context.total_tokens
            return PolicyResult(
                allowed=True,
                metadata={"role": role, "used": current_used + context.total_tokens, "limit": limit},
            )


class AsyncRolePolicy(AsyncBasePolicy):
    def __init__(
        self,
        role_limits: Optional[Dict[str, Union[int, float]]] = None,
        user_roles: Optional[Dict[str, str]] = None,
        default_role: str = "guest",
        default_limit: Union[int, float] = 50_000,
    ) -> None:
        self.role_limits = role_limits or {
            "admin": float("inf"),
            "developer": 1_000_000,
            "guest": 50_000,
        }
        self.user_roles = user_roles or {}
        self.default_role = default_role
        self.default_limit = default_limit
        self._lock = asyncio.Lock()
        self._state: Dict[str, int] = {}

    def get_role(self, context: PolicyContext) -> str:
        if "role" in context.metadata:
            return str(context.metadata["role"])
        return self.user_roles.get(context.user_id, self.default_role)

    async def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        role = self.get_role(context)
        limit = self.role_limits.get(role, self.default_limit)

        async with self._lock:
            current_used = self._state.get(context.user_id, 0)
            if limit != float("inf") and current_used + context.total_tokens > limit:
                return PolicyResult(
                    allowed=False,
                    reason=f"Role '{role}' token limit ({int(limit):,}) exceeded",
                    metadata={"role": role, "used": current_used, "limit": limit},
                )

            self._state[context.user_id] = current_used + context.total_tokens
            return PolicyResult(
                allowed=True,
                metadata={"role": role, "used": current_used + context.total_tokens, "limit": limit},
            )
