"""
storage/async_memory.py
-----------------------
Async in-memory storage backend using asyncio.Lock.
"""

import asyncio
from token_guard.storage.async_base import AsyncBaseStorage
from token_guard.storage.models import UserUsage


class AsyncInMemoryStorage(AsyncBaseStorage):
    """
    Async in-memory storage backend using a dictionary and asyncio.Lock.
    """

    def __init__(self) -> None:
        self._usage: dict[str, UserUsage] = {}
        self._lock = asyncio.Lock()

    async def add_usage(
        self, user_id: str, input_tokens: int, output_tokens: int
    ) -> None:
        async with self._lock:
            if user_id not in self._usage:
                self._usage[user_id] = UserUsage()
            self._usage[user_id].input_tokens += input_tokens
            self._usage[user_id].output_tokens += output_tokens

    async def get_usage(self, user_id: str) -> UserUsage:
        async with self._lock:
            u = self._usage.get(user_id)
            if u is None:
                return UserUsage()
            return UserUsage(u.input_tokens, u.output_tokens)

    async def reset_usage(self, user_id: str) -> None:
        async with self._lock:
            self._usage.pop(user_id, None)

    async def all_users(self) -> dict[str, UserUsage]:
        async with self._lock:
            return {
                uid: UserUsage(u.input_tokens, u.output_tokens)
                for uid, u in self._usage.items()
            }
