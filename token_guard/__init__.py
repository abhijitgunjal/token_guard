"""
token_guard
-----------
Track LLM token usage, enforce limits, and trigger alerts.

Pluggable counter backends : OpenAI, Groq, OpenRouter, AWS Bedrock, custom
Pluggable storage backends : Memory, Redis, SQLite, custom
"""

from token_guard.main import TokenGuard, TrackResult

# Storage
from token_guard.storage import (
    UserUsage,
    BaseStorage,
    InMemoryStorage,
    RedisStorage,
    SQLiteStorage,
    StorageFactory,
)

# Alert system
from token_guard.alert import AlertManager, BaseAlertHandler, ConsoleAlertHandler

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
    "UserUsage", "BaseStorage", "InMemoryStorage",
    "RedisStorage", "SQLiteStorage", "StorageFactory",
    "AlertManager", "BaseAlertHandler", "ConsoleAlertHandler",
    "LimitManager",
    "BaseTokenCounter", "OpenAITokenCounter", "GroqTokenCounter",
    "OpenRouterTokenCounter", "BedrockTokenCounter", "CounterFactory",
    # Deprecated — access still works but emits DeprecationWarning:
    # "UsageTracker", "TokenCounter",
]

__version__ = "0.3.0"
