"""
async_main.py
------------
AsyncTokenGuard — the single public entry point for async LLM tracking.
"""

from __future__ import annotations
from typing import List, Optional, Union

from token_guard.alert import BaseAlertHandler
from token_guard.async_alert import AsyncAlertManager, AsyncBaseAlertHandler
from token_guard.counters.base import BaseTokenCounter
from token_guard.counters.openai import OpenAITokenCounter
from token_guard.engine.evaluator import AsyncPolicyEvaluator
from token_guard.limiter import LimitManager
from token_guard.main import TrackResult
from token_guard.policies.base import AsyncBasePolicy, BasePolicy
from token_guard.policies.models import PolicyContext
from token_guard.storage.async_base import AsyncBaseStorage
from token_guard.storage.async_memory import AsyncInMemoryStorage
from token_guard.storage.models import UserUsage


class AsyncTokenGuard:
    """
    High-level asynchronous API for tracking and enforcing LLM token usage.
    """

    def __init__(
        self,
        max_tokens: Optional[int] = None,
        counter: Optional[BaseTokenCounter] = None,
        model: str = "gpt-4",
        storage: Optional[AsyncBaseStorage] = None,
        alert_handlers: Optional[list[BaseAlertHandler | AsyncBaseAlertHandler]] = None,
        policy: Optional[Union[BasePolicy, AsyncBasePolicy]] = None,
        policies: Optional[List[Union[BasePolicy, AsyncBasePolicy]]] = None,
    ) -> None:
        self._counter: Optional[BaseTokenCounter] = counter
        self._model = model
        self._counter_initialised = counter is not None

        self._storage: AsyncBaseStorage = storage or AsyncInMemoryStorage()
        self.max_tokens = max_tokens if max_tokens is not None else 0
        self._limiter = LimitManager(max_tokens=self.max_tokens) if max_tokens is not None else None
        self._alert = AsyncAlertManager(handlers=alert_handlers)

        all_policies: List[Union[BasePolicy, AsyncBasePolicy]] = []
        if policy is not None:
            all_policies.append(policy)
        if policies is not None:
            all_policies.extend(policies)

        self.evaluator = AsyncPolicyEvaluator(policies=all_policies)

    def _get_counter(self) -> BaseTokenCounter:
        """Return the counter, initialising the default lazily if needed."""
        if self._counter is None:
            self._counter = OpenAITokenCounter(model=self._model)
            self._counter_initialised = True
        return self._counter

    async def _record_and_check(
        self,
        user_id: str,
        input_tokens: int,
        output_tokens: int,
        provider: str,
    ) -> TrackResult:
        """
        Persist usage, evaluate policies, enforce limits, fire alerts, and return a TrackResult.
        """
        total_tokens = input_tokens + output_tokens
        context = PolicyContext(
            user_id=user_id,
            model=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

        policy_res = await self.evaluator.evaluate(context, storage=self._storage)

        if not policy_res.allowed:
            cumulative = await self._storage.get_usage(user_id)
            exceeded = True
            utilization = self._limiter.utilization(cumulative) if self._limiter else 1.0
            await self._alert.trigger(user_id, cumulative, self.max_tokens)
        else:
            await self._storage.add_usage(user_id, input_tokens, output_tokens)
            cumulative = await self._storage.get_usage(user_id)
            limiter_exceeded = self._limiter.check(cumulative) if self._limiter else False
            utilization = self._limiter.utilization(cumulative) if self._limiter else 0.0
            exceeded = limiter_exceeded
            if exceeded:
                await self._alert.trigger(user_id, cumulative, self.max_tokens)

        return TrackResult(
            user_id=user_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cumulative_usage=cumulative,
            limit=self.max_tokens,
            limit_exceeded=exceeded,
            utilization=utilization,
            provider=provider,
            storage_backend=type(self._storage).__name__,
            policy_result=policy_res,
        )

    @property
    def provider(self) -> str:
        """Provider name of the active counter backend, or ``'direct'`` if none."""
        if self._counter is not None:
            return self._counter.provider
        return "direct"

    @property
    def storage_backend(self) -> str:
        """Class name of the active storage backend."""
        return type(self._storage).__name__

    async def track(
        self,
        user_id: str,
        input_text: str,
        output_text: str,
    ) -> TrackResult:
        if not user_id:
            raise ValueError("user_id must be a non-empty string.")
        input_text = input_text or ""
        output_text = output_text or ""

        counter = self._get_counter()
        input_tokens = counter.count(input_text)
        output_tokens = counter.count(output_text)

        return await self._record_and_check(user_id, input_tokens, output_tokens, counter.provider)

    async def track_usage(
        self,
        user_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> TrackResult:
        if not user_id:
            raise ValueError("user_id must be a non-empty string.")
        if input_tokens < 0:
            raise ValueError(f"input_tokens must be >= 0, got {input_tokens}.")
        if output_tokens < 0:
            raise ValueError(f"output_tokens must be >= 0, got {output_tokens}.")

        return await self._record_and_check(user_id, input_tokens, output_tokens, "direct")

    async def get_usage(self, user_id: str) -> UserUsage:
        """Retrieve current cumulative usage for a user without tracking."""
        return await self._storage.get_usage(user_id)

    async def reset_usage(self, user_id: str) -> None:
        """Clear all recorded usage for a user."""
        await self._storage.reset_usage(user_id)

    async def all_users(self) -> dict[str, UserUsage]:
        """Return usage for all tracked users."""
        return await self._storage.all_users()
