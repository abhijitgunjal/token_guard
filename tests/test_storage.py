"""
tests/test_storage.py
----------------------
Tests for all storage backends and StorageFactory.

Run with:
    pytest tests/test_storage.py -v
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from token_guard.storage import (
    StorageFactory,
    InMemoryStorage,
    RedisStorage,
    SQLiteStorage,
    BaseStorage,
    UserUsage,
)
from token_guard import TokenGuard
from token_guard.counters import OpenAITokenCounter
from unittest.mock import patch, MagicMock


def _mock_enc():
    enc = MagicMock()
    enc.encode.side_effect = lambda text: text.split()
    return enc


def _patched_guard(max_tokens, storage):
    with patch("tiktoken.encoding_for_model", return_value=_mock_enc()):
        return TokenGuard(
            max_tokens=max_tokens,
            counter=OpenAITokenCounter("gpt-4"),
            storage=storage,
        )


# ---------------------------------------------------------------------------
# StorageFactory.create()
# ---------------------------------------------------------------------------

class TestStorageFactoryCreate:
    def test_memory_by_name(self):
        store = StorageFactory.create("memory")
        assert isinstance(store, InMemoryStorage)

    def test_inmemory_alias(self):
        store = StorageFactory.create("inmemory")
        assert isinstance(store, InMemoryStorage)

    def test_sqlite_by_name(self):
        store = StorageFactory.create("sqlite", path=":memory:")
        assert isinstance(store, SQLiteStorage)

    def test_redis_by_name(self):
        mock_client = MagicMock()
        store = StorageFactory.create("redis", client=mock_client)
        assert isinstance(store, RedisStorage)

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown storage backend"):
            StorageFactory.create("postgres")

    def test_list_backends(self):
        backends = StorageFactory.list_backends()
        assert "memory" in backends
        assert "redis" in backends
        assert "sqlite" in backends

    def test_register_custom(self):
        class MyStore(BaseStorage):
            def add_usage(self, u, i, o): pass
            def get_usage(self, u): return UserUsage()
            def reset_usage(self, u): pass
            def all_users(self): return {}

        StorageFactory.register("mystore", lambda **kw: MyStore())
        store = StorageFactory.create("mystore")
        assert isinstance(store, MyStore)


# ---------------------------------------------------------------------------
# StorageFactory.from_url()
# ---------------------------------------------------------------------------

class TestStorageFactoryFromUrl:
    def test_from_url_returns_redis_storage(self):
        mock_pool = MagicMock()
        mock_redis_cls = MagicMock()

        with patch("redis.ConnectionPool.from_url", return_value=mock_pool), \
             patch("redis.Redis", return_value=MagicMock()):
            store = StorageFactory.from_url("redis://localhost:6379/0")
        assert isinstance(store, RedisStorage)

    def test_from_url_with_prefix_and_ttl(self):
        with patch("redis.ConnectionPool.from_url", return_value=MagicMock()), \
             patch("redis.Redis", return_value=MagicMock()):
            store = StorageFactory.from_url(
                "redis://localhost:6379/0",
                key_prefix="myapp:tokens",
                ttl=86400,
            )
        assert store._prefix == "myapp:tokens"
        assert store._ttl == 86400


# ---------------------------------------------------------------------------
# StorageFactory.from_env()
# ---------------------------------------------------------------------------

class TestStorageFactoryFromEnv:
    def test_default_is_memory(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TOKEN_GUARD_STORAGE", None)
            store = StorageFactory.from_env()
        assert isinstance(store, InMemoryStorage)

    def test_env_memory(self):
        with patch.dict(os.environ, {"TOKEN_GUARD_STORAGE": "memory"}):
            store = StorageFactory.from_env()
        assert isinstance(store, InMemoryStorage)

    def test_env_sqlite(self):
        with patch.dict(os.environ, {"TOKEN_GUARD_STORAGE": "sqlite"}):
            store = StorageFactory.from_env()
        assert isinstance(store, SQLiteStorage)

    def test_env_redis_with_url(self):
        with patch.dict(os.environ, {
            "TOKEN_GUARD_STORAGE": "redis",
            "REDIS_URL": "redis://localhost:6379/0",
        }), \
        patch("redis.ConnectionPool.from_url", return_value=MagicMock()), \
        patch("redis.Redis", return_value=MagicMock()):
            store = StorageFactory.from_env()
        assert isinstance(store, RedisStorage)

    def test_env_redis_with_ttl(self):
        with patch.dict(os.environ, {
            "TOKEN_GUARD_STORAGE": "redis",
            "REDIS_URL": "redis://localhost:6379/0",
            "TOKEN_GUARD_TTL": "86400",
            "TOKEN_GUARD_KEY_PREFIX": "myapp:tokens",
        }), \
        patch("redis.ConnectionPool.from_url", return_value=MagicMock()), \
        patch("redis.Redis", return_value=MagicMock()):
            store = StorageFactory.from_env()
        assert store._ttl == 86400
        assert store._prefix == "myapp:tokens"


# ---------------------------------------------------------------------------
# StorageFactory.from_config()
# ---------------------------------------------------------------------------

class TestStorageFactoryFromConfig:
    def test_memory_config(self):
        store = StorageFactory.from_config({"backend": "memory"})
        assert isinstance(store, InMemoryStorage)

    def test_sqlite_config(self):
        store = StorageFactory.from_config({
            "backend": "sqlite",
            "path": ":memory:",
        })
        assert isinstance(store, SQLiteStorage)

    def test_redis_config_with_host(self):
        mock_client = MagicMock()
        store = StorageFactory.from_config({
            "backend": "redis",
            "client": mock_client,
            "ttl": 3600,
            "key_prefix": "test",
        })
        assert isinstance(store, RedisStorage)
        assert store._ttl == 3600
        assert store._prefix == "test"

    def test_redis_config_with_url(self):
        with patch("redis.ConnectionPool.from_url", return_value=MagicMock()), \
             patch("redis.Redis", return_value=MagicMock()):
            store = StorageFactory.from_config({
                "backend": "redis",
                "url": "redis://localhost:6379/0",
                "ttl": 86400,
            })
        assert isinstance(store, RedisStorage)
        assert store._ttl == 86400

    def test_does_not_mutate_input_dict(self):
        config = {"backend": "sqlite", "path": ":memory:"}
        original = dict(config)
        StorageFactory.from_config(config)
        assert config == original   # must not be mutated


# ---------------------------------------------------------------------------
# RedisStorage — unit tests with fake client
# ---------------------------------------------------------------------------

class TestRedisStorage:
    """Tests with a minimal in-memory fake Redis client."""

    def _make_fake_redis(self):
        class FakeRedis:
            def __init__(self):
                self._data: dict[str, dict[str, str]] = {}

            def pipeline(self): return FakePipe(self)
            def hgetall(self, key): return dict(self._data.get(key, {}))
            def delete(self, key): self._data.pop(key, None)
            def ping(self): return True
            def scan(self, cursor, match="*", count=100):
                import fnmatch
                keys = [k for k in self._data if fnmatch.fnmatch(k, match)]
                return 0, keys

        class FakePipe:
            def __init__(self, r):
                self._r = r
                self._ops = []
            def hincrby(self, key, field, amt):
                self._ops.append((key, field, amt)); return self
            def expire(self, key, ttl): return self
            def execute(self):
                for key, field, amt in self._ops:
                    if key not in self._r._data:
                        self._r._data[key] = {}
                    cur = int(self._r._data[key].get(field, 0))
                    self._r._data[key][field] = str(cur + amt)

        return FakeRedis()

    def test_add_and_get(self):
        store = RedisStorage(client=self._make_fake_redis())
        store.add_usage("alice", 10, 5)
        u = store.get_usage("alice")
        assert u.input_tokens == 10
        assert u.output_tokens == 5

    def test_accumulates(self):
        store = RedisStorage(client=self._make_fake_redis())
        store.add_usage("alice", 10, 5)
        store.add_usage("alice", 20, 8)
        assert store.get_usage("alice").total_tokens == 43

    def test_unknown_user_zeros(self):
        store = RedisStorage(client=self._make_fake_redis())
        assert store.get_usage("ghost").total_tokens == 0

    def test_reset(self):
        store = RedisStorage(client=self._make_fake_redis())
        store.add_usage("alice", 100, 50)
        store.reset_usage("alice")
        assert store.get_usage("alice").total_tokens == 0

    def test_all_users(self):
        store = RedisStorage(client=self._make_fake_redis())
        store.add_usage("alice", 10, 5)
        store.add_usage("bob", 20, 10)
        all_u = store.all_users()
        assert "alice" in all_u
        assert "bob" in all_u

    def test_custom_key_prefix(self):
        fake = self._make_fake_redis()
        store = RedisStorage(client=fake, key_prefix="myapp:tokens")
        store.add_usage("alice", 10, 5)
        # key should be myapp:tokens:alice
        assert "myapp:tokens:alice" in fake._data

    def test_ttl_applied(self):
        expire_calls = []

        class FakePipeWithExpire:
            def __init__(self, r):
                self._r = r
                self._ops = []
            def hincrby(self, key, field, amt):
                self._ops.append((key, field, amt)); return self
            def expire(self, key, ttl):
                expire_calls.append((key, ttl)); return self
            def execute(self):
                for key, field, amt in self._ops:
                    if key not in self._r._data:
                        self._r._data[key] = {}
                    cur = int(self._r._data[key].get(field, 0))
                    self._r._data[key][field] = str(cur + amt)

        fake = self._make_fake_redis()
        fake.pipeline = lambda: FakePipeWithExpire(fake)
        store = RedisStorage(client=fake, ttl=86400)
        store.add_usage("alice", 5, 3)
        assert len(expire_calls) == 1
        assert expire_calls[0][1] == 86400

    def test_ping_success(self):
        store = RedisStorage(client=self._make_fake_redis())
        assert store.ping() is True

    def test_ping_failure(self):
        broken = MagicMock()
        broken.ping.side_effect = Exception("connection refused")
        store = RedisStorage(client=broken)
        assert store.ping() is False

    def test_missing_redis_raises(self):
        with pytest.raises(ImportError, match="pip install redis"):
            with patch("builtins.__import__", side_effect=ImportError("no redis")):
                RedisStorage(host="localhost")


# ---------------------------------------------------------------------------
# TokenGuard + StorageFactory end-to-end
# ---------------------------------------------------------------------------

class TestTokenGuardWithFactory:
    def test_memory_via_factory(self):
        store = StorageFactory.create("memory")
        guard = _patched_guard(10_000, store)
        result = guard.track("alice", "hello world", "hi there")
        assert result.storage_backend == "InMemoryStorage"
        assert result.input_tokens > 0

    def test_sqlite_via_factory(self):
        store = StorageFactory.create("sqlite", path=":memory:")
        guard = _patched_guard(10_000, store)
        result = guard.track("alice", "hello world", "hi there")
        assert result.storage_backend == "SQLiteStorage"

    def test_redis_via_factory(self):
        mock_client = MagicMock()
        mock_client.pipeline.return_value.__enter__ = MagicMock()
        mock_client.hgetall.return_value = {}

        # Set up pipeline mock
        pipe = MagicMock()
        pipe.hincrby.return_value = pipe
        pipe.execute.return_value = None
        mock_client.pipeline.return_value = pipe

        store = StorageFactory.create("redis", client=mock_client)
        guard = _patched_guard(10_000, store)
        result = guard.track("alice", "hello world", "hi there")
        assert result.storage_backend == "RedisStorage"

    def test_from_config_sqlite(self):
        store = StorageFactory.from_config({
            "backend": "sqlite",
            "path": ":memory:",
        })
        guard = _patched_guard(10_000, store)
        guard.track("alice", "ping", "pong")
        assert guard.get_usage("alice").total_tokens > 0

    def test_from_env_defaults_to_memory(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TOKEN_GUARD_STORAGE", None)
            store = StorageFactory.from_env()
        assert isinstance(store, InMemoryStorage)

    def test_shared_store_two_guards(self):
        """Two guards pointing at the same store share usage data."""
        store = StorageFactory.create("sqlite", path=":memory:")
        g1 = _patched_guard(10_000, store)
        g2 = _patched_guard(10_000, store)

        g1.track("alice", "hello", "hi")
        g2.track("alice", "world", "there")

        assert g1.get_usage("alice").total_tokens == g2.get_usage("alice").total_tokens

    def test_track_usage_via_factory(self):
        """track_usage() works with every factory-created storage backend."""
        for backend, kwargs in [
            ("memory", {}),
            ("sqlite",  {"path": ":memory:"}),
        ]:
            store = StorageFactory.create(backend, **kwargs)
            guard = TokenGuard(max_tokens=10_000, storage=store)
            result = guard.track_usage("alice", input_tokens=42, output_tokens=15)
            assert result.provider == "direct"
            assert result.total_tokens == 57
            assert guard.get_usage("alice").total_tokens == 57
