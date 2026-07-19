"""
token_guard.storage
--------------------
Pluggable storage backends for per-user token usage.

Backends
--------
InMemoryStorage  — default, zero deps, lost on restart
RedisStorage     — persistent, distributed, requires ``pip install redis``
SQLiteStorage    — persistent, zero extra deps, single-server

Factory (recommended for configurable apps)
-------------------------------------------
StorageFactory.create("memory")
StorageFactory.create("redis", host="...", ttl=86400)
StorageFactory.create("sqlite", path="usage.db")
StorageFactory.from_url("redis://...")
StorageFactory.from_env()           # driven by TOKEN_GUARD_STORAGE env var
StorageFactory.from_config({...})   # driven by a config dict

Quick import::

    from token_guard.storage import StorageFactory
    from token_guard.storage import InMemoryStorage, RedisStorage, SQLiteStorage
    from token_guard.storage import BaseStorage   # for custom backends
"""

from token_guard.storage.models import UserUsage
from token_guard.storage.base import BaseStorage
from token_guard.storage.memory import InMemoryStorage
from token_guard.storage.redis import RedisStorage
from token_guard.storage.sqlite import SQLiteStorage
from token_guard.storage.factory import StorageFactory

from token_guard.storage.async_base import AsyncBaseStorage
from token_guard.storage.async_memory import AsyncInMemoryStorage
from token_guard.storage.async_redis import AsyncRedisStorage
from token_guard.storage.async_sqlite import AsyncSQLiteStorage

__all__ = [
    "UserUsage",
    "BaseStorage",
    "InMemoryStorage",
    "RedisStorage",
    "SQLiteStorage",
    "StorageFactory",
    "AsyncBaseStorage",
    "AsyncInMemoryStorage",
    "AsyncRedisStorage",
    "AsyncSQLiteStorage",
]
