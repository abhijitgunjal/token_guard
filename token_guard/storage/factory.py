"""
storage/factory.py
------------------
StorageFactory — create the right storage backend from a simple
string name or a config dict.

This is the recommended way to configure storage in your application,
especially when the backend should be driven by environment variables
or a config file.

Usage::

    # By name
    store = StorageFactory.create("memory")
    store = StorageFactory.create("sqlite")
    store = StorageFactory.create("redis")

    # With options
    store = StorageFactory.create("redis", host="redis.myapp.com", ttl=86400)
    store = StorageFactory.create("sqlite", path="token_usage.db")

    # From environment variable  (STORAGE=redis or STORAGE=memory)
    store = StorageFactory.from_env()

    # From a config dict (e.g. loaded from config.yaml / settings.py)
    store = StorageFactory.from_config({
        "backend": "redis",
        "host": "redis.myapp.com",
        "port": 6379,
        "password": "secret",
        "ttl": 86400,
        "key_prefix": "myapp:tokens",
    })

    # Register a custom backend
    StorageFactory.register("dynamodb", lambda **kw: MyDynamoStorage(**kw))
"""

from __future__ import annotations
import os
from typing import Any, Callable
from token_guard.storage.base import BaseStorage


# Registry: name → callable(**kwargs) -> BaseStorage
_REGISTRY: dict[str, Callable[..., BaseStorage]] = {}


def _register_defaults() -> None:
    from token_guard.storage.memory import InMemoryStorage
    from token_guard.storage.redis import RedisStorage
    from token_guard.storage.sqlite import SQLiteStorage

    _REGISTRY.update({
        "memory":   lambda **kw: InMemoryStorage(),
        "inmemory": lambda **kw: InMemoryStorage(),   # alias
        "redis":    lambda **kw: RedisStorage(**kw),
        "sqlite":   lambda **kw: SQLiteStorage(**kw),
    })


class StorageFactory:
    """
    Factory for creating storage backends by name or config dict.

    Supports:
        - ``"memory"``  → InMemoryStorage  (default, zero deps)
        - ``"redis"``   → RedisStorage     (requires pip install redis)
        - ``"sqlite"``  → SQLiteStorage    (zero deps, file-based)
        - any custom backend registered via ``StorageFactory.register()``
    """

    @classmethod
    def create(cls, backend: str = "memory", **kwargs: Any) -> BaseStorage:
        """
        Create a storage backend by name.

        Args:
            backend:  Backend name — ``"memory"``, ``"redis"``, ``"sqlite"``.
            **kwargs: Options passed directly to the backend constructor.

        Returns:
            A configured BaseStorage instance.

        Raises:
            ValueError: If the backend name is not registered.

        Examples::

            # In-memory (default, no config needed)
            store = StorageFactory.create("memory")

            # Redis with all options
            store = StorageFactory.create(
                "redis",
                host="redis.myapp.com",
                port=6379,
                password="secret",
                ttl=86400,           # expire usage after 24 h
                key_prefix="myapp:tokens",
                max_connections=20,
            )

            # Redis from URL
            store = StorageFactory.create(
                "redis_url",
                url="redis://:secret@redis.myapp.com:6379/0",
                ttl=86400,
            )

            # SQLite (file-based, no extra deps)
            store = StorageFactory.create("sqlite", path="usage.db")
        """
        if not _REGISTRY:
            _register_defaults()

        key = backend.lower().replace("-", "_")
        if key not in _REGISTRY:
            available = ", ".join(sorted(_REGISTRY))
            raise ValueError(
                f"Unknown storage backend '{backend}'. "
                f"Available: {available}. "
                f"Use StorageFactory.register() to add a custom backend."
            )
        return _REGISTRY[key](**kwargs)

    @classmethod
    def from_url(cls, url: str, **kwargs: Any) -> BaseStorage:
        """
        Create a RedisStorage directly from a Redis URL.

        Args:
            url:      Redis URL, e.g.
                      ``"redis://localhost:6379/0"``
                      ``"redis://:password@host:6379/0"``
                      ``"rediss://host:6380/0"``  (TLS)
            **kwargs: Extra options (``key_prefix``, ``ttl``, etc.)

        Example::

            store = StorageFactory.from_url(
                "redis://:secret@redis.myapp.com:6379/0",
                key_prefix="myapp:tokens",
                ttl=86400,
            )
        """
        from token_guard.storage.redis import RedisStorage
        return RedisStorage.from_url(url, **kwargs)

    @classmethod
    def from_env(
        cls,
        env_var: str = "TOKEN_GUARD_STORAGE",
        redis_url_var: str = "REDIS_URL",
        **kwargs: Any,
    ) -> BaseStorage:
        """
        Create a storage backend driven by environment variables.

        Reads ``TOKEN_GUARD_STORAGE`` (default: ``"memory"``) to pick
        the backend.  If it is ``"redis"`` and ``REDIS_URL`` is set,
        uses that URL automatically.

        Args:
            env_var:       Env var that holds the backend name.
            redis_url_var: Env var that holds the Redis URL
                           (used when backend is ``"redis"``).
            **kwargs:      Extra options forwarded to the backend.

        Environment variables::

            TOKEN_GUARD_STORAGE=memory            → InMemoryStorage
            TOKEN_GUARD_STORAGE=sqlite            → SQLiteStorage("token_guard.db")
            TOKEN_GUARD_STORAGE=redis             → RedisStorage(host="localhost")
            TOKEN_GUARD_STORAGE=redis
            REDIS_URL=redis://:pw@host:6379/0     → RedisStorage.from_url(...)

        Example .env file::

            TOKEN_GUARD_STORAGE=redis
            REDIS_URL=redis://:mypassword@redis.myapp.com:6379/0
            TOKEN_GUARD_TTL=86400
            TOKEN_GUARD_KEY_PREFIX=myapp:tokens

        Example usage::

            import os
            from token_guard.storage import StorageFactory
            from token_guard import TokenGuard

            store = StorageFactory.from_env()
            guard = TokenGuard(max_tokens=10_000, storage=store)
        """
        backend = os.getenv(env_var, "memory").lower().strip()

        # Pull extra config from env vars if not already in kwargs
        if "ttl" not in kwargs:
            raw_ttl = os.getenv("TOKEN_GUARD_TTL")
            if raw_ttl:
                kwargs["ttl"] = int(raw_ttl)

        if "key_prefix" not in kwargs:
            prefix = os.getenv("TOKEN_GUARD_KEY_PREFIX")
            if prefix:
                kwargs["key_prefix"] = prefix

        # If backend is redis and REDIS_URL is set, use from_url path
        if backend == "redis":
            redis_url = os.getenv(redis_url_var)
            if redis_url:
                return cls.from_url(redis_url, **kwargs)

        return cls.create(backend, **kwargs)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> BaseStorage:
        """
        Create a storage backend from a config dictionary.

        The dict must have a ``"backend"`` key.  All other keys are
        forwarded to the backend constructor as keyword arguments.

        Args:
            config: Configuration dictionary.

        Example::

            # In your settings.py / config.yaml loader:
            config = {
                "backend": "redis",
                "host": "redis.myapp.com",
                "port": 6379,
                "password": "secret",
                "ttl": 86400,
                "key_prefix": "myapp:tokens",
            }
            store = StorageFactory.from_config(config)

            # Or for SQLite:
            store = StorageFactory.from_config({
                "backend": "sqlite",
                "path": "/var/data/token_usage.db",
            })
        """
        config = dict(config)   # don't mutate caller's dict
        backend = config.pop("backend", "memory")

        # Special case: redis with a URL key
        if backend == "redis" and "url" in config:
            url = config.pop("url")
            return cls.from_url(url, **config)

        return cls.create(backend, **config)

    @classmethod
    def register(
        cls,
        name: str,
        factory_fn: Callable[..., BaseStorage],
    ) -> None:
        """
        Register a custom storage backend.

        Args:
            name:       Unique backend name (case-insensitive).
            factory_fn: Callable ``(**kwargs) -> BaseStorage``.

        Example::

            from token_guard.storage import BaseStorage, StorageFactory
            from token_guard.storage.models import UserUsage

            class DynamoDBStorage(BaseStorage):
                def __init__(self, table_name="token_guard", **kwargs):
                    import boto3
                    self._table = boto3.resource("dynamodb").Table(table_name)

                def add_usage(self, user_id, input_tokens, output_tokens):
                    self._table.update_item(...)

                def get_usage(self, user_id) -> UserUsage:
                    ...

                def reset_usage(self, user_id):
                    ...

                def all_users(self) -> dict[str, UserUsage]:
                    ...

            StorageFactory.register(
                "dynamodb",
                lambda **kw: DynamoDBStorage(**kw),
            )

            store = StorageFactory.create("dynamodb", table_name="my_tokens")
        """
        if not _REGISTRY:
            _register_defaults()
        _REGISTRY[name.lower()] = factory_fn

    @classmethod
    def list_backends(cls) -> list[str]:
        """Return sorted list of all registered backend names."""
        if not _REGISTRY:
            _register_defaults()
        return sorted(_REGISTRY)


