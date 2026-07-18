"""
storage/base.py
---------------
Abstract base class for all storage backends.

Every backend (in-memory, Redis, SQLite, PostgreSQL, DynamoDB …) must
subclass BaseStorage and implement the four methods below.

Minimal custom backend example::

    from token_guard.storage.base import BaseStorage
    from token_guard.storage.models import UserUsage

    class MyDBStorage(BaseStorage):
        def add_usage(self, user_id, input_tokens, output_tokens):
            db.execute(
                "INSERT INTO usage ... ON CONFLICT DO UPDATE ...",
                (user_id, input_tokens, output_tokens)
            )

        def get_usage(self, user_id) -> UserUsage:
            row = db.fetchone("SELECT input, output FROM usage WHERE id=?", user_id)
            return UserUsage(*row) if row else UserUsage()

        def reset_usage(self, user_id):
            db.execute("DELETE FROM usage WHERE id=?", user_id)

        def all_users(self) -> dict[str, UserUsage]:
            rows = db.fetchall("SELECT id, input, output FROM usage")
            return {r[0]: UserUsage(r[1], r[2]) for r in rows}
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

    @abc.abstractmethod
    def reset_usage(self, user_id: str) -> None:
        """Delete all usage data for a user."""

    @abc.abstractmethod
    def all_users(self) -> dict[str, UserUsage]:
        """Return a snapshot of usage for every tracked user."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"
