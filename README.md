# 🛡️ token_guard

> Track LLM token usage per user, enforce limits, and fire alerts —
> across **OpenAI, Groq, OpenRouter, AWS Bedrock**, and any custom provider.
> Storage is pluggable: **in-memory**, **Redis**, or **SQLite** out of the box.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://github.com/abhijitgunjal/token_guard/actions/workflows/publish.yml/badge.svg)](https://github.com/abhijitgunjal/token_guard/actions)

---

## Table of Contents

- [Features](#-features)
- [Installation](#-installation)
  - [Install from GitHub Packages](#install-from-github-packages)
  - [Install from source](#install-from-source)
- [Quick Start](#-quick-start)
- [Token Counting — Providers](#-token-counting--providers)
  - [OpenAI](#openai-default)
  - [Groq](#groq)
  - [OpenRouter](#openrouter)
  - [AWS Bedrock](#aws-bedrock)
  - [Auto-detect provider](#auto-detect-provider)
  - [Custom counter backend](#custom-counter-backend)
  - [Provider accuracy table](#provider-accuracy-table)
- [Storage Backends](#-storage-backends)
  - [In-Memory (default)](#in-memory-default)
  - [Redis](#redis-production)
  - [SQLite](#sqlite)
  - [Configure via environment variables](#configure-via-environment-variables)
  - [Configure via config dict](#configure-via-config-dict)
  - [Custom storage backend](#custom-storage-backend)
- [Alert System](#-alert-system)
  - [Console (default)](#console-default)
  - [Slack](#slack)
  - [Custom alert handler](#custom-alert-handler)
- [FastAPI Integration](#-fastapi-integration)
- [TrackResult — response fields](#-trackresult--response-fields)
- [Project Structure](#-project-structure)
- [Running Tests](#-running-tests)
- [Roadmap](#-roadmap)
- [License](#-license)

---

## ✨ Features

| Feature | Detail |
|---|---|
| **Multi-provider token counting** | OpenAI (exact), Groq, OpenRouter, AWS Bedrock |
| **Exact tracking** | `track_usage()` accepts API-reported counts — always 100% accurate |
| **Pluggable storage** | In-memory, Redis, SQLite — swap with one line |
| **Per-user tracking** | Cumulative counters keyed by `user_id` |
| **Limit enforcement** | Configurable `max_tokens`; checked on every call |
| **Alert system** | Console by default; Slack, email, webhook — fully extensible |
| **Auto-detect provider** | `CounterFactory.auto("model-name")` picks the right backend |
| **Config-driven** | Drive storage from env vars, config dict, or Redis URL |
| **FastAPI ready** | Drop-in middleware pattern included |
| **137 tests** | Full offline test suite — CI safe |

---

## 📦 Installation

### Install from GitHub Packages

This package is published to **GitHub Packages** (GitHub's private/public package registry).

#### Step 1 — Authenticate with GitHub Packages

Create a GitHub Personal Access Token (PAT) with `read:packages` scope:

1. Go to **GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)**
2. Click **Generate new token (classic)**
3. Select scope: `read:packages`
4. Copy the token

#### Step 2 — Configure pip to use GitHub Packages

Create or edit `~/.pip/pip.conf` (Linux/macOS) or `%APPDATA%\pip\pip.ini` (Windows):

```ini
[global]
extra-index-url = https://yourname:YOUR_GITHUB_TOKEN@pip.pkg.github.com/yourname/
```

Or set it inline per-install:

```bash
pip install token-guard \
  --index-url https://yourname:YOUR_GITHUB_TOKEN@pip.pkg.github.com/yourname/
```

Or use environment variables (recommended for CI/CD):

```bash
export GITHUB_TOKEN=ghp_your_token_here
pip install token-guard \
  --index-url https://yourname:${GITHUB_TOKEN}@pip.pkg.github.com/yourname/
```

#### Step 3 — Install the package

```bash
# Core only (OpenAI/tiktoken)
pip install token-guard

# With Redis storage support
pip install "token-guard[redis]"

# With Groq exact counting (HuggingFace tokenizers)
pip install "token-guard[groq]"

# With AWS Bedrock exact counting
pip install "token-guard[bedrock]"

# With FastAPI
pip install "token-guard[fastapi]"

# Everything
pip install "token-guard[all]"
```

#### Using in requirements.txt

```txt
# requirements.txt
--extra-index-url https://yourname:${GITHUB_TOKEN}@pip.pkg.github.com/yourname/
token-guard==0.3.0
token-guard[redis]==0.3.0
```

#### Using in pyproject.toml

```toml
[tool.poetry.dependencies]
token-guard = { version = "0.3.0", source = "github-packages" }

[[tool.poetry.source]]
name = "github-packages"
url = "https://pip.pkg.github.com/yourname/"
priority = "supplemental"
```

---

### Install from source

```bash
git clone https://github.com/yourname/token-guard.git
cd token-guard

pip install -e .                  # core
pip install -e ".[redis]"         # + Redis
pip install -e ".[groq]"          # + Groq exact counting
pip install -e ".[bedrock]"       # + AWS Bedrock exact counting
pip install -e ".[fastapi]"       # + FastAPI
pip install -e ".[dev]"           # + pytest, coverage
pip install -e ".[all]"           # everything
```

---

## 🚀 Quick Start

```python
from token_guard import TokenGuard

# Create a guard — 5,000 token limit per user
guard = TokenGuard(max_tokens=5_000)

# —————————————————————————————————————————————————————————————————
# Option 1 — Exact tracking (recommended for production)
# Pass the token counts directly from your LLM API response.
# Always 100% accurate — includes system prompts, chat templates, etc.
# —————————————————————————————————————————————————————————————————
# After calling your LLM:
#   completion = openai_client.chat.completions.create(...)
#   usage = completion.usage

result = guard.track_usage(
    user_id="alice",
    input_tokens=42,              # usage.prompt_tokens
    output_tokens=15,             # usage.completion_tokens
)

# —————————————————————————————————————————————————————————————————
# Option 2 — Text-based estimation (useful for pre-flight checks)
# Estimates token counts from raw text before or without an API call.
# —————————————————————————————————————————————————————————————————
result = guard.track(
    user_id="alice",
    input_text="What is the capital of France?",
    output_text="The capital of France is Paris.",
)

# Both methods return the same TrackResult:
print(result.provider)                         # "direct" (track_usage) or "openai" (track)
print(result.storage_backend)                  # InMemoryStorage
print(result.input_tokens)                     # exact or estimated
print(result.output_tokens)
print(result.total_tokens)                     # this request
print(result.cumulative_usage.total_tokens)    # lifetime for alice
print(result.limit_exceeded)                   # False
print(f"{result.utilization:.1%}")             # % of limit used
```

---

## 🔢 Token Counting — Providers

### OpenAI (default)

Uses `tiktoken` — the exact same tokenizer OpenAI uses internally.

```python
from token_guard import TokenGuard
from token_guard.counters import OpenAITokenCounter

guard = TokenGuard(
    max_tokens=10_000,
    counter=OpenAITokenCounter(model="gpt-4o"),  # or gpt-4, gpt-3.5-turbo, etc.
)

result = guard.track("alice", input_text, output_text)
print(result.provider)   # openai
```

---

### Groq

Groq hosts open-source models (LLaMA-3, Mixtral, Gemma).
Uses `tiktoken cl100k_base` as an approximation (~95% accurate).
For exact counts, pass `use_transformers=True`.

```python
from token_guard import TokenGuard
from token_guard.counters import GroqTokenCounter

# Approximate (default — no extra deps)
guard = TokenGuard(
    max_tokens=10_000,
    counter=GroqTokenCounter(model="llama-3.3-70b-versatile"),
)

# Exact (requires: pip install transformers)
guard = TokenGuard(
    max_tokens=10_000,
    counter=GroqTokenCounter(
        model="llama-3.3-70b-versatile",
        use_transformers=True,
        hf_model_id="meta-llama/Meta-Llama-3-70B",
    ),
)
```

Supported Groq models: `llama-3.3-70b-versatile`, `llama-3.1-70b-versatile`,
`llama-3.1-8b-instant`, `llama3-70b-8192`, `mixtral-8x7b-32768`, `gemma2-9b-it`, and more.

---

### OpenRouter

OpenRouter proxies many providers under one API.
Model slugs follow the `provider/model` pattern.

```python
from token_guard import TokenGuard
from token_guard.counters import OpenRouterTokenCounter

# OpenAI models via OpenRouter — tiktoken exact
guard = TokenGuard(
    max_tokens=10_000,
    counter=OpenRouterTokenCounter("openai/gpt-4o"),
)

# Anthropic models via OpenRouter — character-ratio estimator (~85%)
guard = TokenGuard(
    max_tokens=10_000,
    counter=OpenRouterTokenCounter("anthropic/claude-3-5-sonnet"),
)

# LLaMA via OpenRouter — tiktoken approximation (~95%)
guard = TokenGuard(
    max_tokens=10_000,
    counter=OpenRouterTokenCounter("meta-llama/llama-3.1-70b-instruct"),
)
```

---

### AWS Bedrock

Bedrock model IDs follow the `vendor.model-name` pattern.

```python
from token_guard import TokenGuard
from token_guard.counters import BedrockTokenCounter

# Approximate — zero extra deps (character-ratio estimator for Anthropic/Amazon)
guard = TokenGuard(
    max_tokens=10_000,
    counter=BedrockTokenCounter("anthropic.claude-3-5-sonnet-20241022-v2:0"),
)

# tiktoken approximation for Meta/Mistral on Bedrock (~95% accurate)
guard = TokenGuard(
    max_tokens=10_000,
    counter=BedrockTokenCounter("meta.llama3-70b-instruct-v1:0"),
)

# Exact — calls AWS CountTokens API (requires: pip install boto3 + IAM permission)
guard = TokenGuard(
    max_tokens=10_000,
    counter=BedrockTokenCounter(
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        use_bedrock_api=True,
        aws_region="us-east-1",
    ),
)
```

---

### Auto-detect provider

`CounterFactory.auto()` detects the right backend from the model string.

```python
from token_guard import TokenGuard
from token_guard.counters import CounterFactory

models = [
    "gpt-4o",                                       # → openai
    "llama-3.3-70b-versatile",                      # → groq
    "openai/gpt-4o",                                # → openrouter
    "anthropic/claude-3-5-sonnet",                  # → openrouter
    "anthropic.claude-3-5-sonnet-20241022-v2:0",   # → bedrock
    "meta.llama3-70b-instruct-v1:0",               # → bedrock
]

for model in models:
    counter = CounterFactory.auto(model)
    guard = TokenGuard(max_tokens=5_000, counter=counter)
    print(f"{model:<50} → {guard.provider}")
```

---

### Custom counter backend

Add any provider in ~5 lines by subclassing `BaseTokenCounter`:

```python
from token_guard.counters import BaseTokenCounter, CounterFactory
from token_guard import TokenGuard

class VertexAITokenCounter(BaseTokenCounter):
    @property
    def provider(self) -> str:
        return "vertexai"

    def count(self, text: str) -> int:
        # Use Google's countTokens API or sentencepiece locally
        import vertexai
        model = vertexai.generative_models.GenerativeModel("gemini-1.5-pro")
        return model.count_tokens(text).total_tokens

# Register once at app startup
CounterFactory.register("vertexai", lambda model, **kw: VertexAITokenCounter())

# Use anywhere
guard = TokenGuard(
    max_tokens=10_000,
    counter=CounterFactory.create("vertexai", "gemini-1.5-pro"),
)
```

---

### Provider accuracy table

| Provider | Models | Method | Accuracy |
|---|---|---|---|
| `openai` | gpt-4*, gpt-3.5-turbo*, embeddings | tiktoken — exact | ✅ 100% |
| `groq` | llama-3, mixtral, gemma | tiktoken cl100k | ~95% |
| `groq` + `use_transformers=True` | any HuggingFace model | AutoTokenizer — exact | ✅ 100% |
| `openrouter` | openai/*, meta-llama/*, mistralai/* | tiktoken cl100k | ~95% |
| `openrouter` | anthropic/*, cohere/* | char ÷ 3.5 estimator | ~85% |
| `bedrock` | meta.*, mistral.* | tiktoken cl100k | ~95% |
| `bedrock` | anthropic.*, amazon.* | char ÷ 3.5 estimator | ~85% |
| `bedrock` + `use_bedrock_api=True` | any Bedrock model | AWS CountTokens API — exact | ✅ 100% |
| **any provider** | — | `track_usage()` with API-reported counts | ✅ **100%** |

> **Note:** Use `track_usage()` whenever your LLM API response includes token counts.
> Use `track()` for pre-flight estimation before making an API call.

---

## 💾 Storage Backends

Storage is fully pluggable via `StorageFactory`.
The backend can be changed with a single line — no other code changes needed.

### In-Memory (default)

Zero dependencies. Data is lost when the process restarts.
Good for development and single-process apps.

```python
from token_guard import TokenGuard

guard = TokenGuard(max_tokens=10_000)  # uses InMemoryStorage by default
```

Or explicitly:

```python
from token_guard import TokenGuard, StorageFactory

guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.create("memory"),
)
```

---

### Redis (production)

Persistent, distributed, safe for multi-worker deployments.
Requires: `pip install "token-guard[redis]"` or `pip install redis`

```python
from token_guard import TokenGuard, StorageFactory

# Simple host/port
guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.create(
        "redis",
        host="localhost",
        port=6379,
        password="your-redis-password",   # optional
        ttl=86400,                         # reset usage every 24h (optional)
        key_prefix="myapp:tokens",         # namespace keys (optional)
        max_connections=20,                # connection pool size (optional)
    ),
)

# From Redis URL (recommended for cloud/12-factor apps)
guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.from_url(
        "redis://:your-password@redis.myapp.com:6379/0",
        ttl=86400,
        key_prefix="myapp:tokens",
    ),
)

# Pass your own existing redis client
import redis
r = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)

from token_guard.storage import RedisStorage
guard = TokenGuard(
    max_tokens=10_000,
    storage=RedisStorage(client=r, ttl=86400),
)
```

**Data layout in Redis:**

```
Key:    token_guard:<user_id>   (Hash)
Fields: input_tokens, output_tokens

Example:
  HGETALL token_guard:alice
  → { "input_tokens": "142", "output_tokens": "310" }
```

**Health check at startup:**

```python
from token_guard.storage import RedisStorage

store = RedisStorage(host="redis.myapp.com")
if not store.ping():
    raise RuntimeError("Redis is not reachable — check connection settings")
```

---

### SQLite

Persistent, zero extra dependencies, good for single-server apps.

```python
from token_guard import TokenGuard, StorageFactory

guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.create("sqlite", path="token_usage.db"),
)

# In-memory SQLite — useful for testing
guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.create("sqlite", path=":memory:"),
)
```

---

### Configure via environment variables

Drive the storage backend entirely from environment variables — no code changes
needed between environments.

```bash
# .env (development)
TOKEN_GUARD_STORAGE=memory

# .env (staging)
TOKEN_GUARD_STORAGE=sqlite

# .env (production)
TOKEN_GUARD_STORAGE=redis
REDIS_URL=redis://:your-password@redis.myapp.com:6379/0
TOKEN_GUARD_TTL=86400
TOKEN_GUARD_KEY_PREFIX=myapp:tokens
```

```python
from token_guard import TokenGuard, StorageFactory

# Reads TOKEN_GUARD_STORAGE (and REDIS_URL if redis)
guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.from_env(),
)
```

This is the recommended pattern for production — the same code runs in every
environment and the storage backend is controlled entirely by config.

---

### Configure via config dict

Use when your app loads config from a YAML/JSON file or Django/Flask settings.

```python
from token_guard import TokenGuard, StorageFactory

# From a settings dict (e.g. loaded from config.yaml)
storage_config = {
    "backend": "redis",
    "url": "redis://:your-password@redis.myapp.com:6379/0",
    "ttl": 86400,
    "key_prefix": "myapp:tokens",
}

guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.from_config(storage_config),
)
```

SQLite example:

```python
guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.from_config({
        "backend": "sqlite",
        "path": "/var/data/token_usage.db",
    }),
)
```

---

### Custom storage backend

Implement `BaseStorage` to connect any data store
(PostgreSQL, DynamoDB, MongoDB, etc.):

```python
from token_guard.storage import BaseStorage, StorageFactory
from token_guard.storage.models import UserUsage
from token_guard import TokenGuard

class PostgresStorage(BaseStorage):
    def __init__(self, dsn: str):
        import psycopg2
        self._conn = psycopg2.connect(dsn)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                user_id TEXT PRIMARY KEY,
                input_tokens INT DEFAULT 0,
                output_tokens INT DEFAULT 0
            )
        """)

    def add_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> None:
        self._conn.execute("""
            INSERT INTO token_usage (user_id, input_tokens, output_tokens)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                input_tokens  = token_usage.input_tokens  + EXCLUDED.input_tokens,
                output_tokens = token_usage.output_tokens + EXCLUDED.output_tokens
        """, (user_id, input_tokens, output_tokens))
        self._conn.commit()

    def get_usage(self, user_id: str) -> UserUsage:
        row = self._conn.execute(
            "SELECT input_tokens, output_tokens FROM token_usage WHERE user_id = %s",
            (user_id,)
        ).fetchone()
        return UserUsage(*row) if row else UserUsage()

    def reset_usage(self, user_id: str) -> None:
        self._conn.execute("DELETE FROM token_usage WHERE user_id = %s", (user_id,))
        self._conn.commit()

    def all_users(self) -> dict[str, UserUsage]:
        rows = self._conn.execute(
            "SELECT user_id, input_tokens, output_tokens FROM token_usage"
        ).fetchall()
        return {r[0]: UserUsage(r[1], r[2]) for r in rows}


# Register and use
StorageFactory.register("postgres", lambda **kw: PostgresStorage(**kw))

guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.create("postgres", dsn="postgresql://localhost/mydb"),
)
```

---

## 🔔 Alert System

Alerts fire automatically when a user exceeds their token limit.

### Console (default)

```
[TokenGuard] ⚠️  LIMIT EXCEEDED — user='alice' | total=5123 tokens | limit=5000
```

No configuration needed.

---

### Slack

```python
import requests
from token_guard import TokenGuard, BaseAlertHandler
from token_guard.storage.models import UserUsage

class SlackAlertHandler(BaseAlertHandler):
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, user_id: str, usage: UserUsage, limit: int) -> None:
        requests.post(self.webhook_url, json={
            "text": (
                f":warning: *Token limit exceeded!*\n"
                f"User: `{user_id}` | "
                f"Used: *{usage.total_tokens:,}* / {limit:,} tokens\n"
                f"Input: {usage.input_tokens:,} | Output: {usage.output_tokens:,}"
            )
        })

guard = TokenGuard(
    max_tokens=5_000,
    alert_handlers=[SlackAlertHandler("https://hooks.slack.com/services/...")],
)
```

---

### Custom alert handler

```python
from token_guard import BaseAlertHandler
from token_guard.storage.models import UserUsage

class EmailAlertHandler(BaseAlertHandler):
    def send(self, user_id: str, usage: UserUsage, limit: int) -> None:
        send_email(
            to="admin@myapp.com",
            subject=f"Token limit exceeded: {user_id}",
            body=f"User {user_id} used {usage.total_tokens:,} / {limit:,} tokens.",
        )

class WebhookAlertHandler(BaseAlertHandler):
    def __init__(self, url: str):
        self.url = url

    def send(self, user_id: str, usage: UserUsage, limit: int) -> None:
        import requests
        requests.post(self.url, json={
            "user_id": user_id,
            "total_tokens": usage.total_tokens,
            "limit": limit,
        })

# Stack multiple handlers
guard = TokenGuard(
    max_tokens=5_000,
    alert_handlers=[
        SlackAlertHandler("https://hooks.slack.com/..."),
        WebhookAlertHandler("https://myapp.com/webhooks/token-alert"),
        EmailAlertHandler(),
    ],
)
```

---

## 🔌 FastAPI Integration

```bash
pip install "token-guard[fastapi]"
cd token-guard
uvicorn example_fastapi:app --reload
```

Interactive docs available at: `http://127.0.0.1:8000/docs`

```bash
# Track tokens — choose provider via ?provider= query param
curl -X POST "http://127.0.0.1:8000/chat?provider=openai&max_tokens=5000" \
     -H "Content-Type: application/json" \
     -d '{"user_id": "alice", "prompt": "What is Python?", "response": "Python is..."}'

# Response:
# {
#   "user_id": "alice",
#   "provider": "openai",
#   "model": "gpt-4o",
#   "input_tokens": 5,
#   "output_tokens": 4,
#   "request_total_tokens": 9,
#   "cumulative_total_tokens": 9,
#   "limit": 5000,
#   "limit_exceeded": false,
#   "utilization_pct": 0.18
# }

# Check usage
curl "http://127.0.0.1:8000/usage/alice?provider=openai"

# Reset usage
curl -X DELETE "http://127.0.0.1:8000/usage/alice?provider=openai"

# List all registered providers
curl http://127.0.0.1:8000/providers

# Health check
curl http://127.0.0.1:8000/health
```

**Integrate TokenGuard into your existing FastAPI app:**

```python
from fastapi import FastAPI, HTTPException
from token_guard import TokenGuard, StorageFactory
from token_guard.counters import CounterFactory

app = FastAPI()

# Configure once at startup
guard = TokenGuard(
    max_tokens=10_000,
    counter=CounterFactory.auto("gpt-4o"),
    storage=StorageFactory.from_env(),   # driven by TOKEN_GUARD_STORAGE env var
)

@app.post("/chat")
async def chat(user_id: str, prompt: str):
    # ... call your LLM ...
    response = call_llm(prompt)

    # After calling your LLM, pass the exact usage from the API response:
    result = guard.track_usage(
        user_id=user_id,
        input_tokens=usage.prompt_tokens,       # exact — from API response
        output_tokens=usage.completion_tokens,
    )

    # Or use text estimation (pre-flight, or when usage data is unavailable):
    # result = guard.track(user_id=user_id, input_text=prompt, output_text=response)

    if result.limit_exceeded:
        raise HTTPException(status_code=429, detail="Token limit exceeded")

    return {"response": response, "tokens_used": result.total_tokens}
```

---

## 📋 TrackResult — response fields

Every call to `guard.track()` and `guard.track_usage()` returns a `TrackResult` dataclass:

| Field | Type | Description |
|---|---|---|
| `user_id` | `str` | The user identifier |
| `input_tokens` | `int` | Tokens counted in the prompt (this request) |
| `output_tokens` | `int` | Tokens counted in the response (this request) |
| `total_tokens` | `int` | `input_tokens + output_tokens` (this request) |
| `cumulative_usage` | `UserUsage` | Lifetime totals for this user |
| `cumulative_usage.input_tokens` | `int` | Lifetime input tokens |
| `cumulative_usage.output_tokens` | `int` | Lifetime output tokens |
| `cumulative_usage.total_tokens` | `int` | Lifetime total tokens |
| `limit` | `int` | The configured `max_tokens` |
| `limit_exceeded` | `bool` | `True` if lifetime total > limit |
| `utilization` | `float` | `total / limit` — e.g. `0.85` = 85% of limit used |
| `provider` | `str` | Counter backend used — e.g. `"openai"`, `"groq"` |
| `storage_backend` | `str` | Storage backend used — e.g. `"RedisStorage"` |

---

## 🏗️ Project Structure

```
token_guard/                          ← project root
│
├── .github/
│   └── workflows/
│       └── publish.yml               ← CI: test on push, publish to PyPI on tag
│
├── token_guard/                      ← importable Python package
│   ├── __init__.py                   ← public API surface
│   ├── main.py                       ← TokenGuard class + TrackResult
│   ├── alert.py                      ← AlertManager, BaseAlertHandler
│   ├── limiter.py                    ← LimitManager
│   ├── tracker.py                    ← backwards-compat shim
│   │
│   ├── counters/                     ← pluggable token counters
│   │   ├── base.py                   ← BaseTokenCounter (ABC — extend this)
│   │   ├── openai.py                 ← OpenAITokenCounter  (tiktoken, exact)
│   │   ├── groq.py                   ← GroqTokenCounter    (tiktoken + HF optional)
│   │   ├── openrouter.py             ← OpenRouterTokenCounter
│   │   ├── bedrock.py                ← BedrockTokenCounter (tiktoken + boto3 optional)
│   │   └── factory.py                ← CounterFactory.create() / .auto() / .register()
│   │
│   └── storage/                      ← pluggable storage backends
│       ├── base.py                   ← BaseStorage (ABC — extend this)
│       ├── models.py                 ← UserUsage dataclass
│       ├── memory.py                 ← InMemoryStorage (default, thread-safe)
│       ├── redis.py                  ← RedisStorage (connection pool, TTL, from_url)
│       ├── sqlite.py                 ← SQLiteStorage (WAL mode, UPSERT)
│       └── factory.py                ← StorageFactory (create/from_url/from_env/from_config)
│
├── tests/
│   ├── test_token_guard.py           ← 101 unit tests (all offline-safe)
│   ├── test_storage.py               ← 36 storage + factory tests
│   └── test_groq_integration.py      ← 8 integration tests (needs GROQ_API_KEY)
│
├── examples/
│   └── multi_provider.py             ← runnable demo of all providers + storage
│
├── .gitignore
├── LICENSE
├── README.md
├── pyproject.toml                    ← package metadata + PyPI config
├── requirements.txt
└── example_fastapi.py                ← multi-provider FastAPI example
```

---

## 🧪 Running Tests

```bash
pip install -e ".[dev]"

# All offline tests (no API keys needed)
pytest tests/test_token_guard.py tests/test_storage.py -v

# Groq integration tests (requires GROQ_API_KEY)
export GROQ_API_KEY=gsk_...
pytest tests/test_groq_integration.py -v -s

# Full suite
pytest tests/ -v

# With coverage report
pytest tests/test_token_guard.py tests/test_storage.py --cov=token_guard --cov-report=term-missing
```

---

## 🗺️ Roadmap

- [x] Multi-provider token counting — OpenAI, Groq, OpenRouter, Bedrock ✅
- [x] Auto-detect provider — `CounterFactory.auto()` ✅
- [x] Pluggable storage — Memory, Redis, SQLite ✅
- [x] `StorageFactory` — `from_env()`, `from_url()`, `from_config()` ✅
- [x] Redis connection pooling + TTL + `from_url()` + `ping()` ✅
- [x] GitHub Actions CI/CD — auto-publish on version tag ✅
- [x] **Exact token tracking** — `track_usage()` with API-reported counts ✅
- [ ] **Async support** — `async def track(...)` for async frameworks
- [ ] **Sliding window limits** — hourly / daily token budgets per user
- [ ] **Budget warnings** — alert at configurable % (e.g. 80%) before hard limit
- [ ] **Per-model cost tracking** — estimate USD cost alongside token counts
- [ ] **Prometheus metrics** — expose `token_guard_tokens_total` counter
- [ ] **Vertex AI / Cohere** — dedicated exact-count backends
- [ ] **PostgreSQL / DynamoDB** — built-in storage backends

---

## 📄 License

MIT ©Abhijit Gunjal — see [LICENSE](LICENSE) for details.
