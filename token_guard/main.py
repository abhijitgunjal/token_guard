"""
main.py
-------
TokenGuard — the single public entry point.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from token_guard.alert import AlertManager, BaseAlertHandler
from token_guard.counters.base import BaseTokenCounter
from token_guard.counters.openai import OpenAITokenCounter
from token_guard.engine.evaluator import PolicyEvaluator
from token_guard.limiter import LimitManager
from token_guard.policies.base import AsyncBasePolicy, BasePolicy
from token_guard.policies.models import PolicyContext, PolicyResult
from token_guard.storage.base import BaseStorage
from token_guard.storage.memory import InMemoryStorage
from token_guard.storage.models import UserUsage


@dataclass
class TrackResult:
    """Structured response returned by TokenGuard.track() and track_usage()."""

    user_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int             # tokens for THIS request only
    cumulative_usage: UserUsage   # lifetime totals for this user
    limit: int
    limit_exceeded: bool
    utilization: float            # fraction of limit consumed (0.0–∞)
    provider: str                 # counter backend used, or "direct" for track_usage()
    storage_backend: str          # which storage backend was used
    policy_result: Optional[PolicyResult] = field(default=None)


class TokenGuard:
    """
    High-level API for tracking and enforcing LLM token usage.
    """

    def __init__(
        self,
        max_tokens: Optional[int] = None,
        counter: Optional[BaseTokenCounter] = None,
        model: str = "gpt-4",
        storage: Optional[BaseStorage] = None,
        alert_handlers: Optional[list[BaseAlertHandler]] = None,
        policy: Optional[Union[BasePolicy, AsyncBasePolicy]] = None,
        policies: Optional[List[Union[BasePolicy, AsyncBasePolicy]]] = None,
    ) -> None:
        self._counter: Optional[BaseTokenCounter] = counter
        self._model = model
        self._counter_initialised = counter is not None

        self._storage: BaseStorage = storage or InMemoryStorage()
        self.max_tokens = max_tokens if max_tokens is not None else 0
        self._limiter = LimitManager(max_tokens=self.max_tokens) if max_tokens is not None else None
        self._alert = AlertManager(handlers=alert_handlers)

        all_policies: List[Union[BasePolicy, AsyncBasePolicy]] = []
        if policy is not None:
            all_policies.append(policy)
        if policies is not None:
            all_policies.extend(policies)

        self.evaluator = PolicyEvaluator(policies=all_policies)

    def _get_counter(self) -> BaseTokenCounter:
        """Return the counter, initialising the default lazily if needed."""
        if self._counter is None:
            self._counter = OpenAITokenCounter(model=self._model)
            self._counter_initialised = True
        return self._counter

    def _record_and_check(
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

        policy_res = self.evaluator.evaluate(context, storage=self._storage)

        if not policy_res.allowed:
            cumulative = self._storage.get_usage(user_id)
            exceeded = True
            utilization = self._limiter.utilization(cumulative) if self._limiter else 1.0
            self._alert.trigger(user_id, cumulative, self.max_tokens)
        else:
            self._storage.add_usage(user_id, input_tokens, output_tokens)
            cumulative = self._storage.get_usage(user_id)
            limiter_exceeded = self._limiter.check(cumulative) if self._limiter else False
            utilization = self._limiter.utilization(cumulative) if self._limiter else 0.0
            exceeded = limiter_exceeded
            if exceeded:
                self._alert.trigger(user_id, cumulative, self.max_tokens)

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

    def track(
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

        return self._record_and_check(user_id, input_tokens, output_tokens, counter.provider)

    def track_usage(
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

        return self._record_and_check(user_id, input_tokens, output_tokens, "direct")

    def get_usage(self, user_id: str) -> UserUsage:
        """Retrieve current cumulative usage for a user without tracking."""
        return self._storage.get_usage(user_id)

    def reset_usage(self, user_id: str) -> None:
        """Clear all recorded usage for a user."""
        self._storage.reset_usage(user_id)

    def all_users(self) -> dict[str, UserUsage]:
        """Return usage for all tracked users."""
        return self._storage.all_users()
