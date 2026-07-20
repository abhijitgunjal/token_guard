"""
token_guard
-----------
Track LLM token usage, enforce limits, and trigger alerts.

Pluggable counter backends : OpenAI, Groq, OpenRouter, AWS Bedrock, custom
Pluggable storage backends : Memory, Redis, SQLite, custom
"""

from token_guard.main import TokenGuard, TrackResult
from token_guard.async_main import AsyncTokenGuard

# Storage
from token_guard.storage import (
    UserUsage,
    BaseStorage,
    InMemoryStorage,
    RedisStorage,
    SQLiteStorage,
    StorageFactory,
    AsyncBaseStorage,
    AsyncInMemoryStorage,
    AsyncRedisStorage,
    AsyncSQLiteStorage,
)

# Alert system
from token_guard.alert import AlertManager, BaseAlertHandler, ConsoleAlertHandler
from token_guard.async_alert import AsyncAlertManager, AsyncBaseAlertHandler

# Limits
from token_guard.limiter import LimitManager

# Counter backends
from token_guard.counters import (
    BaseTokenCounter,
    OpenAITokenCounter,
    GroqTokenCounter,
    OpenRouterTokenCounter,
    BedrockTokenCounter,
    CounterFactory,
)

# Legacy aliases — deprecated, will be removed in a future version
import warnings as _warnings

from token_guard.tracker import UsageTracker as _UsageTracker

def __getattr__(name: str):
    if name == "UsageTracker":
        _warnings.warn(
            "UsageTracker is deprecated and will be removed in a future release. "
            "Use token_guard.storage.InMemoryStorage instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _UsageTracker
    if name == "TokenCounter":
        _warnings.warn(
            "TokenCounter is deprecated and will be removed in a future release. "
            "Use token_guard.counters.OpenAITokenCounter instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return OpenAITokenCounter
    raise AttributeError(f"module 'token_guard' has no attribute {name!r}")

__all__ = [
    "TokenGuard", "TrackResult",
    "AsyncTokenGuard",
    "UserUsage", "BaseStorage", "InMemoryStorage",
    "RedisStorage", "SQLiteStorage", "StorageFactory",
    "AsyncBaseStorage", "AsyncInMemoryStorage", "AsyncRedisStorage", "AsyncSQLiteStorage",
    "AlertManager", "BaseAlertHandler", "ConsoleAlertHandler",
    "AsyncAlertManager", "AsyncBaseAlertHandler",
    "LimitManager",
    "BaseTokenCounter", "OpenAITokenCounter", "GroqTokenCounter",
    "OpenRouterTokenCounter", "BedrockTokenCounter", "CounterFactory",
    # Deprecated — access still works but emits DeprecationWarning:
    # "UsageTracker", "TokenCounter",
]

__version__ = "0.4.1"
