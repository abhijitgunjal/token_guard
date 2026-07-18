"""
tests/test_token_guard.py
--------------------------
Unit tests for token_guard v0.3.0.

All tiktoken network calls are mocked so tests pass offline.

Run with:
    pytest tests/ -v
"""

import math
import pytest
from unittest.mock import patch, MagicMock

from token_guard import (
    TokenGuard,
    TokenCounter,
    OpenAITokenCounter,
    GroqTokenCounter,
    OpenRouterTokenCounter,
    BedrockTokenCounter,
    CounterFactory,
    BaseTokenCounter,
    LimitManager,
    UsageTracker,
    AlertManager,
    BaseAlertHandler,
)
from token_guard.tracker import UserUsage


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_enc():
    enc = MagicMock()
    enc.encode.side_effect = lambda text: text.split()
    return enc

def _patched_openai(model="gpt-4"):
    with patch("tiktoken.encoding_for_model", return_value=_mock_enc()):
        return OpenAITokenCounter(model=model)

def _patched_groq(model="llama-3.3-70b-versatile"):
    with patch("tiktoken.get_encoding", return_value=_mock_enc()):
        return GroqTokenCounter(model=model)

def _patched_openrouter(model="openai/gpt-4o"):
    with patch("tiktoken.get_encoding", return_value=_mock_enc()):
        return OpenRouterTokenCounter(model=model)

def _patched_bedrock(model="meta.llama3-70b-instruct-v1:0"):
    with patch("tiktoken.get_encoding", return_value=_mock_enc()):
        return BedrockTokenCounter(model=model)

def _patched_guard(max_tokens, counter=None, alert_handlers=None):
    c = counter or _patched_openai()
    return TokenGuard(max_tokens=max_tokens, counter=c, alert_handlers=alert_handlers)


# ---------------------------------------------------------------------------
# OpenAITokenCounter
# ---------------------------------------------------------------------------

class TestOpenAITokenCounter:
    def test_empty_string_returns_zero(self):
        assert _patched_openai().count("") == 0

    def test_nonempty_returns_positive(self):
        assert _patched_openai().count("hello world") > 0

    def test_longer_text_has_more_tokens(self):
        c = _patched_openai()
        assert c.count("one two three four five") > c.count("hi")

    def test_provider_name(self):
        assert _patched_openai().provider == "openai"

    def test_unknown_model_falls_back(self):
        with patch("tiktoken.encoding_for_model", side_effect=KeyError("x")), \
             patch("tiktoken.get_encoding", return_value=_mock_enc()):
            c = OpenAITokenCounter(model="unknown-xyz")
            assert c.count("hello world") > 0

    def test_legacy_token_counter_alias(self):
        with patch("tiktoken.encoding_for_model", return_value=_mock_enc()):
            c = TokenCounter(model="gpt-4")
        assert c.provider == "openai"


# ---------------------------------------------------------------------------
# GroqTokenCounter
# ---------------------------------------------------------------------------

class TestGroqTokenCounter:
    def test_provider_name(self):
        assert _patched_groq().provider == "groq"

    def test_empty_string_returns_zero(self):
        assert _patched_groq().count("") == 0

    def test_known_model_word_count(self):
        c = _patched_groq("llama-3.3-70b-versatile")
        assert c.count("hello world") == 2

    def test_unknown_model_falls_back(self):
        with patch("tiktoken.get_encoding", return_value=_mock_enc()):
            c = GroqTokenCounter(model="some-future-model")
        assert c.count("test text") > 0


# ---------------------------------------------------------------------------
# OpenRouterTokenCounter
# ---------------------------------------------------------------------------

class TestOpenRouterTokenCounter:
    def test_provider_name(self):
        assert _patched_openrouter().provider == "openrouter"

    def test_openai_prefix_tiktoken(self):
        c = _patched_openrouter("openai/gpt-4o")
        assert c.counting_method == "tiktoken"
        assert c.count("hello world") == 2

    def test_anthropic_prefix_estimator(self):
        c = OpenRouterTokenCounter(model="anthropic/claude-3-5-sonnet")
        assert c.counting_method == "estimator"

    def test_estimator_positive(self):
        c = OpenRouterTokenCounter(model="anthropic/claude-3-5-sonnet")
        assert c.count("Hello, how are you today?") > 0

    def test_estimator_formula(self):
        c = OpenRouterTokenCounter(model="anthropic/claude-3-5-sonnet")
        assert c.count("x" * 35) == 10  # 35 / 3.5

    def test_empty_returns_zero(self):
        assert OpenRouterTokenCounter("anthropic/claude-3-5-sonnet").count("") == 0

    def test_unknown_prefix_estimator(self):
        c = OpenRouterTokenCounter(model="unknownvendor/some-model")
        assert c.counting_method == "estimator"


# ---------------------------------------------------------------------------
# BedrockTokenCounter
# ---------------------------------------------------------------------------

class TestBedrockTokenCounter:
    def test_provider_name(self):
        assert _patched_bedrock().provider == "bedrock"

    def test_meta_vendor_tiktoken(self):
        c = _patched_bedrock("meta.llama3-70b-instruct-v1:0")
        assert c.counting_method == "tiktoken"
        assert c.count("hello world") == 2

    def test_anthropic_vendor_estimator(self):
        c = BedrockTokenCounter("anthropic.claude-3-5-sonnet-20241022-v2:0")
        assert c.counting_method == "estimator"
        assert c.count("Hello world") > 0

    def test_amazon_vendor_estimator(self):
        c = BedrockTokenCounter("amazon.titan-text-express-v1")
        assert c.counting_method == "estimator"

    def test_estimator_ratio(self):
        c = BedrockTokenCounter("anthropic.claude-3-5-sonnet-20241022-v2:0")
        assert c.count("x" * 35) == 10  # 35 / 3.5

    def test_empty_returns_zero(self):
        assert BedrockTokenCounter("anthropic.claude-3-5-sonnet-20241022-v2:0").count("") == 0

    def test_api_fallback_on_error(self):
        mock_client = MagicMock()
        mock_client.count_tokens.side_effect = Exception("network error")
        c = BedrockTokenCounter.__new__(BedrockTokenCounter)
        c.model = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        c._vendor = "anthropic"
        c._use_bedrock_api = True
        c._bedrock_client = mock_client
        c._encoding = None
        c._chars_per_token = None
        result = c.count("Hello world this is a test")
        assert result > 0


# ---------------------------------------------------------------------------
# CounterFactory
# ---------------------------------------------------------------------------

class TestCounterFactory:
    def test_create_openai(self):
        with patch("tiktoken.encoding_for_model", return_value=_mock_enc()):
            assert CounterFactory.create("openai", "gpt-4o").provider == "openai"

    def test_create_groq(self):
        with patch("tiktoken.get_encoding", return_value=_mock_enc()):
            assert CounterFactory.create("groq", "llama-3.3-70b-versatile").provider == "groq"

    def test_create_openrouter(self):
        with patch("tiktoken.get_encoding", return_value=_mock_enc()):
            assert CounterFactory.create("openrouter", "openai/gpt-4o").provider == "openrouter"

    def test_create_bedrock(self):
        with patch("tiktoken.get_encoding", return_value=_mock_enc()):
            assert CounterFactory.create("bedrock", "meta.llama3-70b-instruct-v1:0").provider == "bedrock"

    def test_create_aws_alias(self):
        with patch("tiktoken.get_encoding", return_value=_mock_enc()):
            assert CounterFactory.create("aws", "meta.llama3-70b-instruct-v1:0").provider == "bedrock"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            CounterFactory.create("nonexistent", "some-model")

    def test_auto_gpt(self):
        with patch("tiktoken.encoding_for_model", return_value=_mock_enc()):
            assert CounterFactory.auto("gpt-4o").provider == "openai"

    def test_auto_bedrock_anthropic(self):
        assert CounterFactory.auto("anthropic.claude-3-5-sonnet-20241022-v2:0").provider == "bedrock"

    def test_auto_openrouter_slash(self):
        with patch("tiktoken.get_encoding", return_value=_mock_enc()):
            assert CounterFactory.auto("openai/gpt-4o").provider == "openrouter"

    def test_auto_groq_llama(self):
        with patch("tiktoken.get_encoding", return_value=_mock_enc()):
            assert CounterFactory.auto("llama-3.3-70b-versatile").provider == "groq"

    def test_auto_bedrock_meta(self):
        with patch("tiktoken.get_encoding", return_value=_mock_enc()):
            assert CounterFactory.auto("meta.llama3-70b-instruct-v1:0").provider == "bedrock"

    def test_register_custom_backend(self):
        class MyCounter(BaseTokenCounter):
            @property
            def provider(self): return "mycustom"
            def count(self, text): return len(text)

        CounterFactory.register("mycustom", lambda model, **kw: MyCounter())
        c = CounterFactory.create("mycustom", "any-model")
        assert c.provider == "mycustom"
        assert c.count("hello") == 5

    def test_list_providers(self):
        providers = CounterFactory.list_providers()
        for p in ("openai", "groq", "openrouter", "bedrock"):
            assert p in providers


# ---------------------------------------------------------------------------
# UsageTracker
# ---------------------------------------------------------------------------

class TestUsageTracker:
    def test_unknown_user_zeros(self):
        assert UsageTracker().get_usage("ghost").total_tokens == 0

    def test_accumulates(self):
        t = UsageTracker()
        t.add_usage("alice", 10, 5)
        t.add_usage("alice", 20, 8)
        assert t.get_usage("alice").total_tokens == 43

    def test_users_isolated(self):
        t = UsageTracker()
        t.add_usage("alice", 100, 50)
        t.add_usage("bob", 10, 5)
        assert t.get_usage("alice").total_tokens == 150
        assert t.get_usage("bob").total_tokens == 15

    def test_reset(self):
        t = UsageTracker()
        t.add_usage("alice", 100, 50)
        t.reset_usage("alice")
        assert t.get_usage("alice").total_tokens == 0


# ---------------------------------------------------------------------------
# LimitManager
# ---------------------------------------------------------------------------

class TestLimitManager:
    def test_under_limit(self):
        assert LimitManager(100).check(UserUsage(30, 30)) is False

    def test_at_limit(self):
        assert LimitManager(100).check(UserUsage(60, 40)) is False

    def test_over_limit(self):
        assert LimitManager(100).check(UserUsage(60, 50)) is True

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            LimitManager(max_tokens=0)

    def test_utilization(self):
        assert LimitManager(200).utilization(UserUsage(100, 100)) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# AlertManager
# ---------------------------------------------------------------------------

class TestAlertManager:
    def test_handler_called(self):
        received = []
        class Cap(BaseAlertHandler):
            def send(self, uid, usage, limit): received.append(uid)
        AlertManager(handlers=[Cap()]).trigger("u", UserUsage(), 100)
        assert received == ["u"]

    def test_failing_handler_no_raise(self):
        class Broken(BaseAlertHandler):
            def send(self, *a): raise RuntimeError("boom")
        AlertManager(handlers=[Broken()]).trigger("u", UserUsage(), 100)


# ---------------------------------------------------------------------------
# TokenGuard integration
# ---------------------------------------------------------------------------

class TestTokenGuardIntegration:
    def test_default_openai(self):
        guard = _patched_guard(10_000)
        r = guard.track("alice", "What is two plus two?", "Four.")
        assert r.provider == "openai"
        assert r.input_tokens > 0
        assert not r.limit_exceeded

    def test_groq_backend(self):
        r = _patched_guard(10_000, counter=_patched_groq()).track("bob", "Hello", "Hi")
        assert r.provider == "groq"

    def test_openrouter_tiktoken(self):
        r = _patched_guard(10_000, counter=_patched_openrouter("openai/gpt-4o")).track("c", "Hello", "Hi")
        assert r.provider == "openrouter"

    def test_openrouter_estimator(self):
        r = _patched_guard(10_000, counter=OpenRouterTokenCounter("anthropic/claude-3-5-sonnet")).track("d", "Hello there", "Hi back")
        assert r.provider == "openrouter"
        assert r.input_tokens > 0

    def test_bedrock_estimator(self):
        r = _patched_guard(10_000, counter=BedrockTokenCounter("anthropic.claude-3-5-sonnet-20241022-v2:0")).track("e", "Hello", "Hi")
        assert r.provider == "bedrock"

    def test_bedrock_tiktoken(self):
        r = _patched_guard(10_000, counter=_patched_bedrock()).track("f", "Hello world", "Goodbye world")
        assert r.provider == "bedrock"

    def test_limit_exceeded_fires_alert(self):
        fired = []
        class Cap(BaseAlertHandler):
            def send(self, uid, usage, limit): fired.append(uid)
        guard = _patched_guard(1, alert_handlers=[Cap()])
        r = guard.track("hank", "a long prompt here", "and a long response")
        assert r.limit_exceeded and "hank" in fired

    def test_provider_property(self):
        assert _patched_guard(1000, counter=_patched_groq()).provider == "groq"

    def test_custom_backend(self):
        class CharCounter(BaseTokenCounter):
            @property
            def provider(self): return "charcount"
            def count(self, text): return len(text)
        r = TokenGuard(max_tokens=1000, counter=CharCounter()).track("ivy", "hello", "world")
        assert r.provider == "charcount"
        assert r.input_tokens == 5
        assert r.output_tokens == 5

    def test_result_has_provider_field(self):
        r = _patched_guard(10_000).track("j", "ping", "pong")
        assert hasattr(r, "provider")
        assert r.provider == "openai"


# ===========================================================================
# Storage backends
# ===========================================================================

from token_guard.storage import (
    BaseStorage,
    InMemoryStorage,
    RedisStorage,
    SQLiteStorage,
)
from token_guard.storage.models import UserUsage as StorageUserUsage


# ---------------------------------------------------------------------------
# InMemoryStorage
# ---------------------------------------------------------------------------

class TestInMemoryStorage:
    def test_unknown_user_returns_zeros(self):
        s = InMemoryStorage()
        assert s.get_usage("ghost").total_tokens == 0

    def test_add_and_get(self):
        s = InMemoryStorage()
        s.add_usage("alice", 10, 5)
        u = s.get_usage("alice")
        assert u.input_tokens == 10
        assert u.output_tokens == 5
        assert u.total_tokens == 15

    def test_accumulates(self):
        s = InMemoryStorage()
        s.add_usage("alice", 10, 5)
        s.add_usage("alice", 20, 8)
        assert s.get_usage("alice").total_tokens == 43

    def test_users_isolated(self):
        s = InMemoryStorage()
        s.add_usage("alice", 100, 50)
        s.add_usage("bob", 10, 5)
        assert s.get_usage("alice").total_tokens == 150
        assert s.get_usage("bob").total_tokens == 15

    def test_reset(self):
        s = InMemoryStorage()
        s.add_usage("alice", 100, 50)
        s.reset_usage("alice")
        assert s.get_usage("alice").total_tokens == 0

    def test_all_users(self):
        s = InMemoryStorage()
        s.add_usage("alice", 10, 5)
        s.add_usage("bob", 20, 10)
        all_u = s.all_users()
        assert "alice" in all_u
        assert "bob" in all_u

    def test_get_returns_copy(self):
        """Mutating the returned UserUsage must not change internal state."""
        s = InMemoryStorage()
        s.add_usage("alice", 10, 5)
        u = s.get_usage("alice")
        u.input_tokens = 999
        assert s.get_usage("alice").input_tokens == 10


# ---------------------------------------------------------------------------
# SQLiteStorage
# ---------------------------------------------------------------------------

class TestSQLiteStorage:
    def test_unknown_user_returns_zeros(self):
        s = SQLiteStorage(":memory:")
        assert s.get_usage("ghost").total_tokens == 0

    def test_add_and_get(self):
        s = SQLiteStorage(":memory:")
        s.add_usage("alice", 10, 5)
        u = s.get_usage("alice")
        assert u.input_tokens == 10
        assert u.output_tokens == 5

    def test_accumulates(self):
        s = SQLiteStorage(":memory:")
        s.add_usage("alice", 10, 5)
        s.add_usage("alice", 20, 8)
        assert s.get_usage("alice").total_tokens == 43

    def test_users_isolated(self):
        s = SQLiteStorage(":memory:")
        s.add_usage("alice", 100, 50)
        s.add_usage("bob", 10, 5)
        assert s.get_usage("alice").total_tokens == 150
        assert s.get_usage("bob").total_tokens == 15

    def test_reset(self):
        s = SQLiteStorage(":memory:")
        s.add_usage("alice", 100, 50)
        s.reset_usage("alice")
        assert s.get_usage("alice").total_tokens == 0

    def test_all_users(self):
        s = SQLiteStorage(":memory:")
        s.add_usage("alice", 10, 5)
        s.add_usage("bob", 20, 10)
        all_u = s.all_users()
        assert set(all_u.keys()) == {"alice", "bob"}

    def test_upsert_is_atomic(self):
        """Multiple adds should accumulate, not overwrite."""
        s = SQLiteStorage(":memory:")
        for _ in range(5):
            s.add_usage("alice", 10, 5)
        u = s.get_usage("alice")
        assert u.input_tokens == 50
        assert u.output_tokens == 25


# ---------------------------------------------------------------------------
# RedisStorage — mocked (no real Redis needed)
# ---------------------------------------------------------------------------

class TestRedisStorageMocked:
    """Tests RedisStorage logic with a fake Redis client."""

    def _make_store(self):
        """Build a RedisStorage backed by a simple in-memory fake."""

        class FakeRedis:
            """Minimal Redis fake: supports pipeline, hincrby, hgetall, delete, scan."""
            def __init__(self):
                self._data: dict[str, dict[str, str]] = {}

            def pipeline(self):
                return FakePipeline(self)

            def hgetall(self, key):
                return dict(self._data.get(key, {}))

            def delete(self, key):
                self._data.pop(key, None)

            def scan(self, cursor, match="*", count=100):
                import fnmatch
                keys = [k for k in self._data if fnmatch.fnmatch(k, match)]
                return 0, keys   # cursor=0 means "done"

        class FakePipeline:
            def __init__(self, redis):
                self._r = redis
                self._ops = []

            def hincrby(self, key, field, amount):
                self._ops.append(("hincrby", key, field, amount))
                return self

            def expire(self, key, ttl):
                return self   # no-op in fake

            def execute(self):
                for op in self._ops:
                    if op[0] == "hincrby":
                        _, key, field, amount = op
                        if key not in self._r._data:
                            self._r._data[key] = {}
                        current = int(self._r._data[key].get(field, 0))
                        self._r._data[key][field] = str(current + amount)

        return RedisStorage(client=FakeRedis())

    def test_unknown_user_returns_zeros(self):
        s = self._make_store()
        assert s.get_usage("ghost").total_tokens == 0

    def test_add_and_get(self):
        s = self._make_store()
        s.add_usage("alice", 10, 5)
        u = s.get_usage("alice")
        assert u.input_tokens == 10
        assert u.output_tokens == 5

    def test_accumulates(self):
        s = self._make_store()
        s.add_usage("alice", 10, 5)
        s.add_usage("alice", 20, 8)
        assert s.get_usage("alice").total_tokens == 43

    def test_reset(self):
        s = self._make_store()
        s.add_usage("alice", 100, 50)
        s.reset_usage("alice")
        assert s.get_usage("alice").total_tokens == 0

    def test_all_users(self):
        s = self._make_store()
        s.add_usage("alice", 10, 5)
        s.add_usage("bob", 20, 10)
        all_u = s.all_users()
        assert "alice" in all_u
        assert "bob" in all_u

    def test_missing_redis_raises(self):
        with pytest.raises(ImportError, match="pip install redis"):
            with patch("builtins.__import__", side_effect=ImportError("no redis")):
                RedisStorage(host="localhost")


# ---------------------------------------------------------------------------
# Custom storage backend
# ---------------------------------------------------------------------------

class TestCustomStorage:
    def test_custom_backend_plugs_in(self):
        """Any BaseStorage subclass works as a drop-in."""

        class DictStorage(BaseStorage):
            def __init__(self):
                self._d: dict[str, tuple[int, int]] = {}

            def add_usage(self, uid, inp, out):
                i, o = self._d.get(uid, (0, 0))
                self._d[uid] = (i + inp, o + out)

            def get_usage(self, uid):
                i, o = self._d.get(uid, (0, 0))
                return StorageUserUsage(i, o)

            def reset_usage(self, uid):
                self._d.pop(uid, None)

            def all_users(self):
                return {u: StorageUserUsage(i, o) for u, (i, o) in self._d.items()}

        guard = _patched_guard(max_tokens=1000, counter=_patched_openai())
        guard._storage = DictStorage()

        guard._storage.add_usage("alice", 10, 5)
        assert guard.get_usage("alice").total_tokens == 15


# ---------------------------------------------------------------------------
# TokenGuard with different storage backends
# ---------------------------------------------------------------------------

class TestTokenGuardStorageIntegration:
    def test_default_uses_memory(self):
        guard = _patched_guard(max_tokens=1000)
        assert guard.storage_backend == "InMemoryStorage"

    def test_sqlite_storage(self):
        store = SQLiteStorage(":memory:")
        counter = _patched_openai()
        guard = TokenGuard(max_tokens=1000, counter=counter, storage=store)
        result = guard.track("alice", "hello world", "hi there")
        assert result.storage_backend == "SQLiteStorage"
        assert result.input_tokens > 0
        # Verify data actually went to SQLite
        assert store.get_usage("alice").total_tokens > 0

    def test_usage_persists_across_guard_instances_sqlite(self):
        """Two TokenGuard instances sharing the same SQLite store share usage."""
        store = SQLiteStorage(":memory:")
        g1 = TokenGuard(max_tokens=10_000, counter=_patched_openai(), storage=store)
        g2 = TokenGuard(max_tokens=10_000, counter=_patched_openai(), storage=store)

        g1.track("alice", "hello", "hi")
        g2.track("alice", "world", "there")

        # Both guards see the same cumulative total
        assert g1.get_usage("alice").total_tokens == g2.get_usage("alice").total_tokens

    def test_result_has_storage_backend_field(self):
        guard = _patched_guard(max_tokens=1000)
        result = guard.track("x", "ping", "pong")
        assert hasattr(result, "storage_backend")

    def test_all_users_returns_all(self):
        store = SQLiteStorage(":memory:")
        guard = TokenGuard(max_tokens=10_000, counter=_patched_openai(), storage=store)
        guard.track("alice", "a", "b")
        guard.track("bob", "c", "d")
        all_u = guard.all_users()
        assert "alice" in all_u
        assert "bob" in all_u


# ---------------------------------------------------------------------------
# track_usage() — exact API-reported token counts
# ---------------------------------------------------------------------------

class TestTokenGuardTrackUsage:
    """Tests for TokenGuard.track_usage() — exact-count tracking path."""

    def _guard(self, max_tokens=10_000, **kwargs):
        return TokenGuard(max_tokens=max_tokens, **kwargs)

    def test_track_usage_basic(self):
        guard = self._guard()
        result = guard.track_usage("alice", input_tokens=42, output_tokens=15)
        assert result.input_tokens == 42
        assert result.output_tokens == 15
        assert result.total_tokens == 57
        assert result.user_id == "alice"

    def test_track_usage_provider_is_direct(self):
        """track_usage() always reports provider='direct' — no counter used."""
        guard = self._guard()
        result = guard.track_usage("alice", input_tokens=10, output_tokens=5)
        assert result.provider == "direct"

    def test_track_usage_accumulates(self):
        guard = self._guard()
        guard.track_usage("alice", input_tokens=10, output_tokens=5)
        guard.track_usage("alice", input_tokens=20, output_tokens=8)
        assert guard.get_usage("alice").total_tokens == 43

    def test_track_usage_limit_exceeded(self):
        guard = self._guard(max_tokens=10)
        result = guard.track_usage("alice", input_tokens=8, output_tokens=5)
        assert result.limit_exceeded is True

    def test_track_usage_alert_fires(self):
        fired = []
        class Cap(BaseAlertHandler):
            def send(self, uid, usage, limit): fired.append(uid)
        guard = self._guard(max_tokens=5, alert_handlers=[Cap()])
        guard.track_usage("hank", input_tokens=4, output_tokens=3)
        assert "hank" in fired

    def test_track_usage_empty_user_id_raises(self):
        guard = self._guard()
        with pytest.raises(ValueError, match="user_id"):
            guard.track_usage("", input_tokens=10, output_tokens=5)

    def test_track_usage_none_user_id_raises(self):
        guard = self._guard()
        with pytest.raises(ValueError, match="user_id"):
            guard.track_usage(None, input_tokens=10, output_tokens=5)

    def test_track_usage_negative_input_raises(self):
        guard = self._guard()
        with pytest.raises(ValueError, match="input_tokens"):
            guard.track_usage("alice", input_tokens=-1, output_tokens=5)

    def test_track_usage_negative_output_raises(self):
        guard = self._guard()
        with pytest.raises(ValueError, match="output_tokens"):
            guard.track_usage("alice", input_tokens=10, output_tokens=-1)

    def test_track_usage_zero_tokens_allowed(self):
        """Zero tokens is valid (e.g. cached prompt, no output)."""
        guard = self._guard()
        result = guard.track_usage("alice", input_tokens=0, output_tokens=0)
        assert result.total_tokens == 0
        assert result.limit_exceeded is False

    def test_track_usage_no_counter_needed(self):
        """track_usage() works without any counter configured."""
        guard = TokenGuard(max_tokens=1_000)  # no counter= arg
        result = guard.track_usage("alice", input_tokens=50, output_tokens=25)
        assert result.total_tokens == 75
        assert result.provider == "direct"

    def test_track_usage_with_sqlite_storage(self):
        store = SQLiteStorage(":memory:")
        guard = TokenGuard(max_tokens=10_000, storage=store)
        guard.track_usage("alice", input_tokens=100, output_tokens=50)
        assert store.get_usage("alice").total_tokens == 150
        assert guard.storage_backend == "SQLiteStorage"

    def test_track_usage_with_memory_storage(self):
        from token_guard.storage import InMemoryStorage
        store = InMemoryStorage()
        guard = TokenGuard(max_tokens=10_000, storage=store)
        guard.track_usage("bob", input_tokens=20, output_tokens=10)
        assert store.get_usage("bob").total_tokens == 30

    def test_track_and_track_usage_share_storage(self):
        """Mixing track() and track_usage() accumulates to the same user."""
        guard = _patched_guard(max_tokens=10_000)
        guard.track("alice", "hello world", "hi there")       # ~4 tokens (mocked)
        guard.track_usage("alice", input_tokens=100, output_tokens=50)
        total = guard.get_usage("alice").total_tokens
        assert total > 150   # track() added some + track_usage() added 150

    def test_track_usage_users_isolated(self):
        guard = self._guard()
        guard.track_usage("alice", input_tokens=50, output_tokens=25)
        guard.track_usage("bob",   input_tokens=10, output_tokens=5)
        assert guard.get_usage("alice").total_tokens == 75
        assert guard.get_usage("bob").total_tokens == 15

    def test_track_usage_cumulative_in_result(self):
        guard = self._guard()
        guard.track_usage("alice", input_tokens=10, output_tokens=5)
        result = guard.track_usage("alice", input_tokens=20, output_tokens=8)
        assert result.cumulative_usage.total_tokens == 43

    def test_track_usage_utilization(self):
        guard = self._guard(max_tokens=100)
        result = guard.track_usage("alice", input_tokens=50, output_tokens=50)
        assert result.utilization == pytest.approx(1.0)
