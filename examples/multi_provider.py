"""
examples/multi_provider.py
---------------------------
Runnable demo of token_guard with every supported provider.

HOW TO RUN
----------
Option A — after installing the package (recommended):
    pip install -e .                        # run once from project root
    python examples/multi_provider.py

Option B — without installing (this file handles it automatically):
    python examples/multi_provider.py       # works from any directory
"""

# ---------------------------------------------------------------------------
# Make "from token_guard import ..." work whether or not the package is
# installed.  We locate the project root (the folder that contains pyproject.toml)
# relative to this file's location and add it to sys.path.
# ---------------------------------------------------------------------------
import sys
from pathlib import Path

# This file lives at <project_root>/examples/multi_provider.py
# So the project root is two levels up from __file__
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Now normal imports work regardless of how the script was launched
# ---------------------------------------------------------------------------
from unittest.mock import patch, MagicMock

from token_guard import TokenGuard
from token_guard.counters import (
    CounterFactory,
    OpenAITokenCounter,
    GroqTokenCounter,
    OpenRouterTokenCounter,
    BedrockTokenCounter,
    BaseTokenCounter,
)

# ---------------------------------------------------------------------------
# Helpers — mock tiktoken so this script runs without internet access.
# Remove the mock patches when running with a real tiktoken install.
# ---------------------------------------------------------------------------

def _mock_enc():
    enc = MagicMock()
    enc.encode.side_effect = lambda text: text.split()
    return enc


PROMPT = "Explain how transformers work in simple terms."
RESPONSE = (
    "Transformers use self-attention to weigh the importance of each word "
    "in the input, allowing the model to understand context across long sequences. "
    "They process all tokens in parallel, making them very efficient on GPUs."
)

SEPARATOR = "─" * 60


def demo_openai():
    print("\n📦 OpenAI (tiktoken — exact)")
    with patch("tiktoken.encoding_for_model", return_value=_mock_enc()):
        guard = TokenGuard(
            max_tokens=10_000,
            counter=OpenAITokenCounter(model="gpt-4o"),
        )
    result = guard.track("alice", PROMPT, RESPONSE)
    _print_result(result)


def demo_groq():
    print("\n⚡ Groq — llama-3.3-70b-versatile")
    with patch("tiktoken.get_encoding", return_value=_mock_enc()):
        guard = TokenGuard(
            max_tokens=10_000,
            counter=GroqTokenCounter(model="llama-3.3-70b-versatile"),
        )
    result = guard.track("alice", PROMPT, RESPONSE)
    _print_result(result)


def demo_openrouter_tiktoken():
    print("\n🌐 OpenRouter — openai/gpt-4o (tiktoken)")
    with patch("tiktoken.get_encoding", return_value=_mock_enc()):
        guard = TokenGuard(
            max_tokens=10_000,
            counter=OpenRouterTokenCounter(model="openai/gpt-4o"),
        )
    result = guard.track("alice", PROMPT, RESPONSE)
    _print_result(result, note=f"counting_method={guard._counter.counting_method}")


def demo_openrouter_estimator():
    print("\n🌐 OpenRouter — anthropic/claude-3-5-sonnet (estimator)")
    guard = TokenGuard(
        max_tokens=10_000,
        counter=OpenRouterTokenCounter(model="anthropic/claude-3-5-sonnet"),
    )
    result = guard.track("alice", PROMPT, RESPONSE)
    _print_result(result, note=f"counting_method={guard._counter.counting_method}")


def demo_bedrock_tiktoken():
    print("\n☁️  AWS Bedrock — meta.llama3-70b-instruct-v1:0 (tiktoken)")
    with patch("tiktoken.get_encoding", return_value=_mock_enc()):
        guard = TokenGuard(
            max_tokens=10_000,
            counter=BedrockTokenCounter(model="meta.llama3-70b-instruct-v1:0"),
        )
    result = guard.track("alice", PROMPT, RESPONSE)
    _print_result(result, note=f"counting_method={guard._counter.counting_method}")


def demo_bedrock_estimator():
    print("\n☁️  AWS Bedrock — anthropic.claude-3-5-sonnet-20241022-v2:0 (estimator)")
    guard = TokenGuard(
        max_tokens=10_000,
        counter=BedrockTokenCounter(
            model="anthropic.claude-3-5-sonnet-20241022-v2:0"
        ),
    )
    result = guard.track("alice", PROMPT, RESPONSE)
    _print_result(result, note=f"counting_method={guard._counter.counting_method}")


def demo_factory_auto():
    print("\n🤖 CounterFactory.auto() — auto-detect from model string")
    models = [
        "gpt-4o",
        "llama-3.3-70b-versatile",
        "openai/gpt-4o",
        "anthropic/claude-3-5-sonnet",
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "meta.llama3-70b-instruct-v1:0",
        "mistral.mixtral-8x7b-instruct-v0:1",
    ]
    for model in models:
        with patch("tiktoken.encoding_for_model", return_value=_mock_enc()), \
             patch("tiktoken.get_encoding", return_value=_mock_enc()):
            counter = CounterFactory.auto(model)
        print(f"  {model:<50} → provider={counter.provider!r}")


def demo_storage_backends():
    print("\n💾 Storage backends")

    from token_guard.storage import InMemoryStorage, SQLiteStorage

    # In-memory (default)
    with patch("tiktoken.encoding_for_model", return_value=_mock_enc()):
        guard_mem = TokenGuard(
            max_tokens=10_000,
            counter=OpenAITokenCounter("gpt-4o"),
            storage=InMemoryStorage(),
        )
    r = guard_mem.track("alice", PROMPT, RESPONSE)
    print(f"  InMemoryStorage  → storage_backend={r.storage_backend}")

    # SQLite
    with patch("tiktoken.encoding_for_model", return_value=_mock_enc()):
        guard_sql = TokenGuard(
            max_tokens=10_000,
            counter=OpenAITokenCounter("gpt-4o"),
            storage=SQLiteStorage(":memory:"),
        )
    r = guard_sql.track("alice", PROMPT, RESPONSE)
    print(f"  SQLiteStorage    → storage_backend={r.storage_backend}")


def demo_custom_backend():
    print("\n🔧 Custom counter backend — character counter")

    class CharTokenCounter(BaseTokenCounter):
        @property
        def provider(self) -> str:
            return "charcount"

        def count(self, text: str) -> int:
            return len(text)

    CounterFactory.register("charcount", lambda model, **kw: CharTokenCounter())
    guard = TokenGuard(
        max_tokens=500,
        counter=CounterFactory.create("charcount", "my-model"),
    )
    result = guard.track("alice", PROMPT, RESPONSE)
    _print_result(result)


def demo_limit_enforcement():
    print("\n🚨 Limit enforcement — tiny budget (max_tokens=10)")
    with patch("tiktoken.encoding_for_model", return_value=_mock_enc()):
        guard = TokenGuard(
            max_tokens=10,
            counter=OpenAITokenCounter(model="gpt-4o"),
        )
    result = guard.track("alice", PROMPT, RESPONSE)
    _print_result(result)
    if result.limit_exceeded:
        print("  ⚠️  Alert fired — you would see this in your alert handler.")


def demo_multi_user():
    print("\n👥 Multi-user tracking")
    with patch("tiktoken.get_encoding", return_value=_mock_enc()):
        guard = TokenGuard(
            max_tokens=100,
            counter=GroqTokenCounter("llama-3.3-70b-versatile"),
        )
    for user in ["alice", "bob", "alice"]:
        guard.track(user, PROMPT[:20], RESPONSE[:30])

    for user in ["alice", "bob"]:
        usage = guard.get_usage(user)
        print(f"  {user}: total={usage.total_tokens} "
              f"(input={usage.input_tokens}, output={usage.output_tokens})")


def demo_track_usage():
    print("\n🎯 track_usage() — exact API-reported token counts")
    print("  (simulating what you'd get from usage.prompt_tokens / usage.completion_tokens)")

    # No counter needed — token guard is purely a bookkeeper here
    guard = TokenGuard(max_tokens=500)

    # Simulate three API calls with exact counts from the provider
    api_calls = [
        {"prompt_tokens": 42, "completion_tokens": 18},
        {"prompt_tokens": 55, "completion_tokens": 30},
        {"prompt_tokens": 38, "completion_tokens": 12},
    ]
    for i, call in enumerate(api_calls, 1):
        result = guard.track_usage(
            "alice",
            input_tokens=call["prompt_tokens"],
            output_tokens=call["completion_tokens"],
        )
        print(f"  call {i}: input={result.input_tokens}, output={result.output_tokens}, "
              f"cumulative={result.cumulative_usage.total_tokens}, "
              f"provider={result.provider}")

    print(f"  Final utilization: {result.utilization:.1%} of {guard.max_tokens} limit")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_result(result, note: str = "") -> None:
    print(f"  provider        : {result.provider}")
    print(f"  storage_backend : {result.storage_backend}")
    print(f"  input_tokens    : {result.input_tokens}")
    print(f"  output_tokens   : {result.output_tokens}")
    print(f"  total (request) : {result.total_tokens}")
    print(f"  cumulative      : {result.cumulative_usage.total_tokens}")
    print(f"  limit_exceeded  : {result.limit_exceeded}")
    print(f"  utilization     : {result.utilization:.2%}")
    if note:
        print(f"  {note}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(SEPARATOR)
    print("  token_guard v0.3.0 — multi-provider demo")
    print(f"  project root: {PROJECT_ROOT}")
    print(SEPARATOR)

    demo_openai()
    demo_groq()
    demo_openrouter_tiktoken()
    demo_openrouter_estimator()
    demo_bedrock_tiktoken()
    demo_bedrock_estimator()
    demo_factory_auto()
    demo_storage_backends()
    demo_custom_backend()
    demo_limit_enforcement()
    demo_multi_user()
    demo_track_usage()

    print(f"\n{SEPARATOR}")
    print("  All demos complete ✅")
    print(SEPARATOR)
