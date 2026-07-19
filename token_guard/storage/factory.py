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
from token_guard.storage.async_base import AsyncBaseStorage


# Registry: name → callable(**kwargs) -> BaseStorage | AsyncBaseStorage
_REGISTRY: dict[str, Callable[..., BaseStorage | AsyncBaseStorage]] = {}


def _register_defaults() -> None:
    from token_guard.storage.memory import InMemoryStorage
    from token_guard.storage.redis import RedisStorage
    from token_guard.storage.sqlite import SQLiteStorage

    from token_guard.storage.async_memory import AsyncInMemoryStorage
    from token_guard.storage.async_redis import AsyncRedisStorage
    from token_guard.storage.async_sqlite import AsyncSQLiteStorage

    _REGISTRY.update({
        "memory":         lambda **kw: InMemoryStorage(),
        "inmemory":       lambda **kw: InMemoryStorage(),   # alias
        "redis":          lambda **kw: RedisStorage(**kw),
        "sqlite":         lambda **kw: SQLiteStorage(**kw),
        "memory_async":   lambda **kw: AsyncInMemoryStorage(),
        "inmemory_async": lambda **kw: AsyncInMemoryStorage(),
        "async_memory":   lambda **kw: AsyncInMemoryStorage(),
        "redis_async":    lambda **kw: AsyncRedisStorage(**kw),
        "async_redis":    lambda **kw: AsyncRedisStorage(**kw),
        "sqlite_async":   lambda **kw: AsyncSQLiteStorage(**kw),
        "async_sqlite":   lambda **kw: AsyncSQLiteStorage(**kw),
    })


class StorageFactory:
    """
    Factory for creating storage backends by name or config dict.

    Supports:
        - ``"memory"``  → InMemoryStorage  (default, zero deps)
        - ``"redis"``   → RedisStorage     (requires pip install redis)
        - ``"sqlite"``  → SQLiteStorage    (zero deps, file-based)
        - ``"memory_async"`` → AsyncInMemoryStorage
        - ``"redis_async"``  → AsyncRedisStorage
        - ``"sqlite_async"`` → AsyncSQLiteStorage
        - any custom backend registered via ``StorageFactory.register()``
    """

    @classmethod
    def create(cls, backend: str = "memory", **kwargs: Any) -> BaseStorage | AsyncBaseStorage:
        """
        Create a storage backend by name.

        Args:
            backend:  Backend name — ``"memory"``, ``"redis"``, ``"sqlite"``, etc.
            **kwargs: Options passed directly to the backend constructor.

        Returns:
            A configured BaseStorage or AsyncBaseStorage instance.

        Raises:
            ValueError: If the backend name is not registered.
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
    def from_url(cls, url: str, **kwargs: Any) -> BaseStorage | AsyncBaseStorage:
        """
        Create a RedisStorage or AsyncRedisStorage directly from a Redis URL.

        Args:
            url:      Redis URL.
            **kwargs: Extra options (``key_prefix``, ``ttl``, etc.)
        """
        async_mode = kwargs.pop("async_mode", False)
        if async_mode:
            from token_guard.storage.async_redis import AsyncRedisStorage
            return AsyncRedisStorage.from_url(url, **kwargs)

        from token_guard.storage.redis import RedisStorage
        return RedisStorage.from_url(url, **kwargs)

    @classmethod
    def from_env(
        cls,
        env_var: str = "TOKEN_GUARD_STORAGE",
        redis_url_var: str = "REDIS_URL",
        **kwargs: Any,
    ) -> BaseStorage | AsyncBaseStorage:
        """
        Create a storage backend driven by environment variables.
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
        is_async = "async" in backend
        if backend in ("redis", "redis_async", "async_redis"):
            redis_url = os.getenv(redis_url_var)
            if redis_url:
                return cls.from_url(redis_url, async_mode=is_async, **kwargs)

        return cls.create(backend, **kwargs)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> BaseStorage | AsyncBaseStorage:
        """
        Create a storage backend from a config dictionary.
        """
        config = dict(config)   # don't mutate caller's dict
        backend = config.pop("backend", "memory")

        # Special case: redis with a URL key
        is_async = "async" in backend
        if backend in ("redis", "redis_async", "async_redis") and "url" in config:
            url = config.pop("url")
            return cls.from_url(url, async_mode=is_async, **config)

        return cls.create(backend, **config)

    @classmethod
    def register(
        cls,
        name: str,
        factory_fn: Callable[..., BaseStorage | AsyncBaseStorage],
    ) -> None:
        """
        Register a custom storage backend.
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


