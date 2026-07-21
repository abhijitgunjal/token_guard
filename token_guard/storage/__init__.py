"""
token_guard.storage
--------------------
Pluggable storage backends for per-user token usage.

Backends
--------
InMemoryStorage   — default, zero deps, lost on restart
RedisStorage      — persistent, distributed, requires ``pip install redis``
SQLiteStorage     — persistent, zero extra deps, single-server
PostgreSQLStorage — persistent, enterprise SQL, requires ``pip install psycopg``
DynamoDBStorage   — persistent, AWS serverless NoSQL, requires ``pip install boto3``

Factory (recommended for configurable apps)
-------------------------------------------
StorageFactory.create("memory")
StorageFactory.create("redis", host="...", ttl=86400)
StorageFactory.create("sqlite", path="usage.db")
StorageFactory.create("postgres", connection_string="postgresql://...")
StorageFactory.create("dynamodb", table_name="token_guard_usage")
StorageFactory.from_url("postgresql://...")
StorageFactory.from_env()           # driven by TOKEN_GUARD_STORAGE env var
StorageFactory.from_config({...})   # driven by a config dict
"""

from token_guard.storage.models import UserUsage
from token_guard.storage.base import BaseStorage
from token_guard.storage.memory import InMemoryStorage
from token_guard.storage.redis import RedisStorage
from token_guard.storage.sqlite import SQLiteStorage
from token_guard.storage.postgres import PostgreSQLStorage, AsyncPostgreSQLStorage
from token_guard.storage.dynamodb import DynamoDBStorage, AsyncDynamoDBStorage
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
    "PostgreSQLStorage",
    "AsyncPostgreSQLStorage",
    "DynamoDBStorage",
    "AsyncDynamoDBStorage",
    "StorageFactory",
    "AsyncBaseStorage",
    "AsyncInMemoryStorage",
    "AsyncRedisStorage",
    "AsyncSQLiteStorage",
]
