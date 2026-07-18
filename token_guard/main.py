"""
main.py
-------
TokenGuard — the single public entry point.

Accepts any BaseStorage backend for pluggable persistence.

Two tracking modes
------------------
1.  ``track(user_id, input_text, output_text)``
    Counts tokens from raw text using the configured counter backend.
    Useful for **pre-flight estimation** before an API call, or when the
    provider's response does not include usage data.

2.  ``track_usage(user_id, input_tokens, output_tokens)``
    Accepts the **exact token counts** reported by the LLM API response
    (e.g. ``usage.prompt_tokens`` from OpenAI / Groq / OpenRouter).
    Recommended for **production** — no re-estimation, no overhead errors.

Examples::

    # Default (in-memory, zero deps)
    guard = TokenGuard(max_tokens=5000)

    # Production: exact counts from API response (no counter needed)
    result = guard.track_usage("alice", input_tokens=42, output_tokens=15)

    # Pre-flight estimation from text
    result = guard.track("alice", input_text=prompt, output_text=response)

    # Redis (persistent, distributed)
    from token_guard.storage import RedisStorage
    guard = TokenGuard(max_tokens=5000, storage=RedisStorage(host="localhost"))

    # SQLite (persistent, no extra deps)
    from token_guard.storage import SQLiteStorage
    guard = TokenGuard(max_tokens=5000, storage=SQLiteStorage("usage.db"))

    # Custom backend
    from token_guard.storage import BaseStorage
    class MyStorage(BaseStorage): ...
    guard = TokenGuard(max_tokens=5000, storage=MyStorage())
"""

from dataclasses import dataclass
from typing import Optional

from token_guard.alert import AlertManager, BaseAlertHandler
from token_guard.counters.base import BaseTokenCounter
from token_guard.counters.openai import OpenAITokenCounter
from token_guard.limiter import LimitManager
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


class TokenGuard:
    """
    High-level API for tracking and enforcing LLM token usage.

    Args:
        max_tokens:      Maximum cumulative tokens allowed per user.
        counter:         A BaseTokenCounter instance. Optional when only
                         ``track_usage()`` is called; required for ``track()``.
                         Defaults to ``OpenAITokenCounter("gpt-4")`` when not
                         provided, for backwards compatibility.
        model:           Shorthand — used only when ``counter=None`` and
                         ``track()`` is called.
        storage:         A BaseStorage instance (default: InMemoryStorage).
                         Pass RedisStorage, SQLiteStorage, or any custom
                         BaseStorage subclass to change where usage is stored.
        alert_handlers:  Optional list of BaseAlertHandler instances.

    Examples::

        # Exact counts from API response — no counter needed
        guard = TokenGuard(max_tokens=10_000)
        result = guard.track_usage("alice", input_tokens=42, output_tokens=15)

        # Text-based estimation
        guard = TokenGuard(
            max_tokens=10_000,
            counter=OpenAITokenCounter("gpt-4o"),
        )
        result = guard.track("alice", input_text=prompt, output_text=response)

        # Redis
        from token_guard.storage import RedisStorage
        guard = TokenGuard(
            max_tokens=10_000,
            storage=RedisStorage(host="redis", port=6379, ttl=86400),
        )

        # SQLite
        from token_guard.storage import SQLiteStorage
        guard = TokenGuard(
            max_tokens=10_000,
            storage=SQLiteStorage("token_usage.db"),
        )
    """

    #: Sentinel indicating no counter was explicitly provided.
    _NO_COUNTER = object()

    def __init__(
        self,
        max_tokens: int,
        counter: Optional[BaseTokenCounter] = None,
        model: str = "gpt-4",
        storage: Optional[BaseStorage] = None,
        alert_handlers: Optional[list[BaseAlertHandler]] = None,
    ) -> None:
        # Store counter as-is; _resolve_counter() is called lazily by track().
        self._counter: Optional[BaseTokenCounter] = counter
        self._model = model               # fallback model for lazy init
        self._counter_initialised = counter is not None

        self._storage: BaseStorage = storage or InMemoryStorage()
        self._limiter = LimitManager(max_tokens=max_tokens)
        self._alert = AlertManager(handlers=alert_handlers)
        self.max_tokens = max_tokens

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
        Persist usage, enforce limits, fire alerts, and return a TrackResult.

        Shared by both ``track()`` and ``track_usage()``.
        """
        self._storage.add_usage(user_id, input_tokens, output_tokens)
        cumulative = self._storage.get_usage(user_id)

        exceeded = self._limiter.check(cumulative)
        utilization = self._limiter.utilization(cumulative)

        if exceeded:
            self._alert.trigger(user_id, cumulative, self.max_tokens)

        return TrackResult(
            user_id=user_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cumulative_usage=cumulative,
            limit=self.max_tokens,
            limit_exceeded=exceeded,
            utilization=utilization,
            provider=provider,
            storage_backend=type(self._storage).__name__,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
        """
        Estimate token counts from text, record usage, enforce limits, fire alerts.

        Use this for **pre-flight estimation** or when the LLM API response does
        not include token counts.  For production use with real API responses,
        prefer :meth:`track_usage` which accepts the exact counts reported by the
        provider.

        Args:
            user_id:     Unique identifier for the calling user.
                         Must be a non-empty string.
            input_text:  The prompt / user message sent to the model.
                         ``None`` is treated as an empty string.
            output_text: The completion / model response received.
                         ``None`` is treated as an empty string.

        Returns:
            :class:`TrackResult` with per-request counts, cumulative totals,
            limit status, and backend info.

        Raises:
            ValueError: If ``user_id`` is empty or ``None``.
        """
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
        """
        Record **exact** token counts from an LLM API response.

        Use this when you already have the token counts reported by the provider
        (e.g. ``usage.prompt_tokens`` / ``usage.completion_tokens`` from the
        OpenAI, Groq, OpenRouter, or Bedrock API response).  This is the
        recommended method for production — it is always 100% accurate because
        it uses the provider's own billing numbers.

        No counter backend is required.

        Args:
            user_id:       Unique identifier for the calling user.
                           Must be a non-empty string.
            input_tokens:  Exact input token count from the API response.
                           Must be >= 0.
            output_tokens: Exact output token count from the API response.
                           Must be >= 0.

        Returns:
            :class:`TrackResult` with exact counts, cumulative totals,
            limit status, and backend info.  ``result.provider`` will be
            ``"direct"`` to indicate no counter was used.

        Raises:
            ValueError: If ``user_id`` is empty/``None``, or if token counts
                        are negative.

        Example::

            # After a Groq API call:
            completion = groq_client.chat.completions.create(...)
            usage = completion.usage

            result = guard.track_usage(
                user_id="alice",
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
            )
        """
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
