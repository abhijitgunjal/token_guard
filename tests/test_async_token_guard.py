"""
tests/test_async_token_guard.py
-------------------------------
Unit tests for AsyncTokenGuard, async storage backends, and async alerts.
"""

import asyncio
import pytest
import fnmatch
from unittest.mock import MagicMock, patch, AsyncMock

from token_guard import AsyncTokenGuard, TrackResult
from token_guard.storage import (
    StorageFactory,
    AsyncInMemoryStorage,
    AsyncRedisStorage,
    AsyncSQLiteStorage,
    UserUsage,
)
from token_guard.counters import OpenAITokenCounter
from token_guard.async_alert import AsyncBaseAlertHandler, AsyncAlertManager
from token_guard.alert import BaseAlertHandler


def _mock_enc():
    enc = MagicMock()
    enc.encode.side_effect = lambda text: text.split()
    return enc


def _patched_async_guard(max_tokens, storage):
    with patch("tiktoken.encoding_for_model", return_value=_mock_enc()):
        return AsyncTokenGuard(
            max_tokens=max_tokens,
            counter=OpenAITokenCounter("gpt-4"),
            storage=storage,
        )


# ---------------------------------------------------------------------------
# StorageFactory.create() for async backends
# ---------------------------------------------------------------------------

class TestAsyncStorageFactoryCreate:
    def test_memory_async_by_name(self):
        store = StorageFactory.create("memory_async")
        assert isinstance(store, AsyncInMemoryStorage)

    def test_inmemory_async_alias(self):
        store = StorageFactory.create("inmemory_async")
        assert isinstance(store, AsyncInMemoryStorage)

    def test_async_memory_alias(self):
        store = StorageFactory.create("async_memory")
        assert isinstance(store, AsyncInMemoryStorage)

    def test_sqlite_async_by_name(self):
        store = StorageFactory.create("sqlite_async", path=":memory:")
        assert isinstance(store, AsyncSQLiteStorage)

    def test_async_sqlite_alias(self):
        store = StorageFactory.create("async_sqlite", path=":memory:")
        assert isinstance(store, AsyncSQLiteStorage)

    def test_redis_async_by_name(self):
        mock_client = MagicMock()
        store = StorageFactory.create("redis_async", client=mock_client)
        assert isinstance(store, AsyncRedisStorage)

    def test_async_redis_alias(self):
        mock_client = MagicMock()
        store = StorageFactory.create("async_redis", client=mock_client)
        assert isinstance(store, AsyncRedisStorage)


# ---------------------------------------------------------------------------
# AsyncInMemoryStorage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAsyncInMemoryStorage:
    async def test_add_and_get(self):
        store = AsyncInMemoryStorage()
        await store.add_usage("alice", 10, 5)
        usage = await store.get_usage("alice")
        assert usage.input_tokens == 10
        assert usage.output_tokens == 5
        assert usage.total_tokens == 15

    async def test_reset(self):
        store = AsyncInMemoryStorage()
        await store.add_usage("alice", 10, 5)
        await store.reset_usage("alice")
        usage = await store.get_usage("alice")
        assert usage.total_tokens == 0

    async def test_all_users(self):
        store = AsyncInMemoryStorage()
        await store.add_usage("alice", 10, 5)
        await store.add_usage("bob", 20, 10)
        users = await store.all_users()
        assert len(users) == 2
        assert users["alice"].total_tokens == 15
        assert users["bob"].total_tokens == 30

    async def test_concurrency(self):
        store = AsyncInMemoryStorage()

        async def worker():
            for _ in range(50):
                await store.add_usage("alice", 1, 1)

        await asyncio.gather(*(worker() for _ in range(5)))
        usage = await store.get_usage("alice")
        assert usage.input_tokens == 250
        assert usage.output_tokens == 250


# ---------------------------------------------------------------------------
# AsyncSQLiteStorage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAsyncSQLiteStorage:
    async def test_sqlite_lifecycle(self):
        store = AsyncSQLiteStorage(path=":memory:")
        try:
            await store.add_usage("alice", 10, 5)
            usage = await store.get_usage("alice")
            assert usage.input_tokens == 10
            assert usage.output_tokens == 5

            await store.add_usage("alice", 5, 2)
            usage = await store.get_usage("alice")
            assert usage.input_tokens == 15
            assert usage.output_tokens == 7

            all_u = await store.all_users()
            assert "alice" in all_u

            await store.reset_usage("alice")
            usage = await store.get_usage("alice")
            assert usage.total_tokens == 0
        finally:
            await store.close()


# ---------------------------------------------------------------------------
# AsyncRedisStorage with Fake Client
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAsyncRedisStorage:
    def _make_fake_async_redis(self):
        class FakeAsyncRedis:
            def __init__(self):
                self._data = {}

            def pipeline(self, transaction=True):
                return FakeAsyncPipe(self)

            async def hgetall(self, key):
                return dict(self._data.get(key, {}))

            async def delete(self, key):
                self._data.pop(key, None)

            async def ping(self):
                return True

            async def scan(self, cursor, match="*", count=100):
                keys = [k for k in self._data if fnmatch.fnmatch(k, match)]
                return 0, keys

        class FakeAsyncPipe:
            def __init__(self, r):
                self._r = r
                self._ops = []

            def hincrby(self, key, field, amt):
                self._ops.append((key, field, amt))
                return self

            def expire(self, key, ttl):
                return self

            async def execute(self):
                for key, field, amt in self._ops:
                    if key not in self._r._data:
                        self._r._data[key] = {}
                    cur = int(self._r._data[key].get(field, 0))
                    self._r._data[key][field] = str(cur + amt)

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        return FakeAsyncRedis()

    async def test_redis_add_get(self):
        fake = self._make_fake_async_redis()
        store = AsyncRedisStorage(client=fake)
        await store.add_usage("alice", 10, 5)
        usage = await store.get_usage("alice")
        assert usage.input_tokens == 10
        assert usage.output_tokens == 5

    async def test_redis_reset_all(self):
        fake = self._make_fake_async_redis()
        store = AsyncRedisStorage(client=fake)
        await store.add_usage("alice", 10, 5)
        await store.add_usage("bob", 20, 10)
        
        users = await store.all_users()
        assert "alice" in users
        assert "bob" in users

        await store.reset_usage("alice")
        usage = await store.get_usage("alice")
        assert usage.total_tokens == 0


# ---------------------------------------------------------------------------
# AsyncAlertManager & Mix of Sync/Async Alerts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAsyncAlertManager:
    async def test_mixed_handlers(self):
        sync_called = []
        async_called = []

        class SimpleSyncHandler(BaseAlertHandler):
            def send(self, user_id, usage, limit):
                sync_called.append((user_id, usage, limit))

        class SimpleAsyncHandler(AsyncBaseAlertHandler):
            async def send(self, user_id, usage, limit):
                async_called.append((user_id, usage, limit))

        manager = AsyncAlertManager(handlers=[SimpleSyncHandler(), SimpleAsyncHandler()])
        usage = UserUsage(100, 50)
        await manager.trigger("alice", usage, 500)

        assert len(sync_called) == 1
        assert len(async_called) == 1
        assert sync_called[0] == ("alice", usage, 500)
        assert async_called[0] == ("alice", usage, 500)


# ---------------------------------------------------------------------------
# AsyncTokenGuard Core
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAsyncTokenGuard:
    async def test_track_usage(self):
        storage = AsyncInMemoryStorage()
        guard = _patched_async_guard(5000, storage)

        result = await guard.track_usage("alice", 42, 18)
        assert isinstance(result, TrackResult)
        assert result.user_id == "alice"
        assert result.input_tokens == 42
        assert result.output_tokens == 18
        assert result.total_tokens == 60
        assert result.cumulative_usage.total_tokens == 60
        assert not result.limit_exceeded

    async def test_track_text(self):
        storage = AsyncInMemoryStorage()
        guard = _patched_async_guard(5000, storage)

        result = await guard.track("alice", "hello world", "welcome user")
        # 2 words input, 2 words output under the mock encoder
        assert result.input_tokens == 2
        assert result.output_tokens == 2
        assert result.total_tokens == 4

    async def test_limit_exceeded(self):
        called = []

        class MockAlert(AsyncBaseAlertHandler):
            async def send(self, user_id, usage, limit):
                called.append(user_id)

        storage = AsyncInMemoryStorage()
        guard = AsyncTokenGuard(max_tokens=100, storage=storage, alert_handlers=[MockAlert()])
        
        result1 = await guard.track_usage("alice", 80, 10)
        assert not result1.limit_exceeded
        assert len(called) == 0

        result2 = await guard.track_usage("alice", 15, 5)
        assert result2.limit_exceeded
        assert len(called) == 1
        assert called[0] == "alice"
