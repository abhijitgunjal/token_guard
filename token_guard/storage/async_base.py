"""
storage/async_base.py
---------------------
Abstract base class for all async storage backends.
"""

import abc
from token_guard.storage.models import UserUsage


class AsyncBaseStorage(abc.ABC):
    """
    Abstract storage backend for per-user token usage (asynchronous).

    Subclass this to persist usage in any async data store.
    """

    @abc.abstractmethod
    async def add_usage(
        self, user_id: str, input_tokens: int, output_tokens: int
    ) -> None:
        """
        Increment token usage for a user.

        Args:
            user_id:       Unique identifier for the user.
            input_tokens:  Prompt tokens to add.
            output_tokens: Completion tokens to add.
        """

    @abc.abstractmethod
    async def get_usage(self, user_id: str) -> UserUsage:
        """
        Return cumulative usage for a user.

        Returns a zeroed UserUsage if the user has no history.
        """

    async def add_and_get_usage(
        self, user_id: str, input_tokens: int, output_tokens: int
    ) -> UserUsage:
        """
        Increment token usage for a user and return updated cumulative totals.
        Can be overridden by subclasses to combine atomic write-and-read.
        """
        await self.add_usage(user_id, input_tokens, output_tokens)
        return await self.get_usage(user_id)

    @abc.abstractmethod
    async def reset_usage(self, user_id: str) -> None:
        """Delete all usage data for a user."""

    @abc.abstractmethod
    async def all_users(self) -> dict[str, UserUsage]:
        """Return a snapshot of usage for every tracked user."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"
