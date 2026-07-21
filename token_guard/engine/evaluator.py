import asyncio
from typing import Any, List, Optional, Union

from token_guard.policies.base import AsyncBasePolicy, BasePolicy
from token_guard.policies.models import PolicyContext, PolicyResult


class PolicyEvaluator:
    def __init__(self, policies: Optional[List[Union[BasePolicy, AsyncBasePolicy]]] = None) -> None:
        self.policies: List[Union[BasePolicy, AsyncBasePolicy]] = policies or []

    def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        """Evaluate all configured policies sequentially. Short-circuits on first rejection."""
        if not self.policies:
            return PolicyResult(allowed=True)

        for policy in self.policies:
            if isinstance(policy, AsyncBasePolicy):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    # If in running event loop, execute in nested thread
                    result = asyncio.run_coroutine_threadsafe(
                        policy.evaluate(context, storage), loop
                    ).result()
                else:
                    result = asyncio.run(policy.evaluate(context, storage))
            else:
                result = policy.evaluate(context, storage)

            if not result.allowed:
                return result

        return PolicyResult(allowed=True)


class AsyncPolicyEvaluator:
    def __init__(self, policies: Optional[List[Union[BasePolicy, AsyncBasePolicy]]] = None) -> None:
        self.policies: List[Union[BasePolicy, AsyncBasePolicy]] = policies or []

    async def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        """Evaluate all configured policies asynchronously. Short-circuits on first rejection."""
        if not self.policies:
            return PolicyResult(allowed=True)

        for policy in self.policies:
            if isinstance(policy, AsyncBasePolicy):
                result = await policy.evaluate(context, storage)
            else:
                result = policy.evaluate(context, storage)

            if not result.allowed:
                return result

        return PolicyResult(allowed=True)
