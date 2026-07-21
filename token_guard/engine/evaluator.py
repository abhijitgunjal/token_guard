import asyncio
import concurrent.futures
from typing import Any, List, Optional, Union

from token_guard.policies.base import AsyncBasePolicy, BasePolicy
from token_guard.policies.models import PolicyContext, PolicyResult


def _run_coro_sync(coro_func, *args, **kwargs) -> Any:
    """
    Safely execute an async coroutine function from synchronous code.
    If an event loop is running on the current thread, executes in a dedicated
    worker thread with its own event loop to prevent event loop deadlocks.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        def _worker():
            new_loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(new_loop)
                return new_loop.run_until_complete(coro_func(*args, **kwargs))
            finally:
                new_loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(_worker).result()
    else:
        return asyncio.run(coro_func(*args, **kwargs))


class PolicyEvaluator:
    def __init__(self, policies: Optional[List[Union[BasePolicy, AsyncBasePolicy]]] = None) -> None:
        self.policies: List[Union[BasePolicy, AsyncBasePolicy]] = policies or []

    def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        """Evaluate all configured policies sequentially. Short-circuits on first rejection."""
        if not self.policies:
            return PolicyResult(allowed=True)

        for policy in self.policies:
            if isinstance(policy, AsyncBasePolicy):
                result = _run_coro_sync(policy.evaluate, context, storage)
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
