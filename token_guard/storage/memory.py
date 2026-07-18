"""
storage/memory.py
-----------------
Default in-memory storage backend.

- Zero dependencies
- Thread-safe (uses threading.Lock)
- Data is lost when the process restarts
- Perfect for: development, testing, single-process apps

For production multi-worker deployments use RedisStorage instead.
"""

import threading
from token_guard.storage.base import BaseStorage
from token_guard.storage.models import UserUsage


class InMemoryStorage(BaseStorage):
    """
    Thread-safe in-memory storage using a plain dict + RLock.

    Data does NOT persist across process restarts.
    """

    def __init__(self) -> None:
        self._usage: dict[str, UserUsage] = {}
        self._lock = threading.RLock()

    def add_usage(
        self, user_id: str, input_tokens: int, output_tokens: int
    ) -> None:
        with self._lock:
            if user_id not in self._usage:
                self._usage[user_id] = UserUsage()
            self._usage[user_id].input_tokens  += input_tokens
            self._usage[user_id].output_tokens += output_tokens

    def get_usage(self, user_id: str) -> UserUsage:
        with self._lock:
            u = self._usage.get(user_id)
            if u is None:
                return UserUsage()
            return UserUsage(u.input_tokens, u.output_tokens)  # return a copy

    def reset_usage(self, user_id: str) -> None:
        with self._lock:
            self._usage.pop(user_id, None)

    def all_users(self) -> dict[str, UserUsage]:
        with self._lock:
            return {
                uid: UserUsage(u.input_tokens, u.output_tokens)
                for uid, u in self._usage.items()
            }
