"""
storage/base.py
---------------
Abstract base class for all storage backends.
"""

import abc
from token_guard.storage.models import UserUsage


class BaseStorage(abc.ABC):
    """
    Abstract storage backend for per-user token usage.

    Subclass this to persist usage in any data store.
    """

    @abc.abstractmethod
    def add_usage(
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
    def get_usage(self, user_id: str) -> UserUsage:
        """
        Return cumulative usage for a user.

        Returns a zeroed UserUsage if the user has no history.
        """

    def add_and_get_usage(
        self, user_id: str, input_tokens: int, output_tokens: int
    ) -> UserUsage:
        """
        Increment token usage for a user and return updated cumulative totals.
        Can be overridden by subclasses to combine atomic write-and-read.
        """
        self.add_usage(user_id, input_tokens, output_tokens)
        return self.get_usage(user_id)

    @abc.abstractmethod
    def reset_usage(self, user_id: str) -> None:
        """Delete all usage data for a user."""

    @abc.abstractmethod
    def all_users(self) -> dict[str, UserUsage]:
        """Return a snapshot of usage for every tracked user."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"
