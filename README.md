<p align="center">
  <img src="https://raw.githubusercontent.com/abhijitgunjal/token_guard/main/assets/banner.png" alt="token_guard — LLM token tracking, limits & alerts" width="900" />
</p>

# TokenGuard

Production-ready token tracking, policy evaluation engines, budget limits, and alerts for LLM applications.

[![PyPI Version](https://img.shields.io/pypi/v/llm-token-guard.svg)](https://pypi.org/project/llm-token-guard/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests Status](https://github.com/abhijitgunjal/token_guard/actions/workflows/publish.yml/badge.svg)](https://github.com/abhijitgunjal/token_guard/actions)

---

<a id="quick-start"></a>
## ⚡ Quick Start

```python
# Sync exact tracking with a Sliding Window Policy
from token_guard import TokenGuard, SlidingWindowPolicy

policy = SlidingWindowPolicy(limit=50_000, window=3600)
guard = TokenGuard(policy=policy)
result = guard.track_usage("alice", input_tokens=42, output_tokens=15)

print(result.total_tokens)                  # 57
print(result.limit_exceeded)                # False
print(result.cumulative_usage.total_tokens) # 57

# Async exact tracking with Token Bucket Policy
from token_guard import AsyncTokenGuard, AsyncTokenBucketPolicy

async_policy = AsyncTokenBucketPolicy(capacity=10_000, refill_rate=100.0)
async_guard = AsyncTokenGuard(policy=async_policy)
result = await async_guard.track_usage("bob", input_tokens=42, output_tokens=15)

print(result.total_tokens)                  # 57
print(result.limit_exceeded)                # False
```

---

<a id="table-of-contents"></a>
## Table of Contents

- [Quick Start](#quick-start)
- [Why TokenGuard?](#why-token-guard)
- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Documentation Guides](#documentation-guides)
  - [Policy Engine](docs/policies.md)
  - [Token Counting & Providers](docs/providers.md)
  - [Storage Backends](docs/storage.md)
  - [PostgreSQL Storage Guide](docs/storage/postgresql.md)
  - [AWS DynamoDB Storage Guide](docs/storage/dynamodb.md)
  - [FastAPI Integration](docs/fastapi.md)
  - [Async Support](docs/async.md)
  - [Custom Backends](docs/custom-backends.md)
- [Provider Compatibility](#provider-compatibility)
- [Project Structure](#project-structure)
- [Examples](#examples)
- [Running Tests](#running-tests)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

<a id="why-token-guard"></a>
## 🧠 Why TokenGuard?

LLM calls are billed per token (inputs + outputs). Unchecked application consumption can quickly lead to unexpected cost spikes, upstream API rate-limiting blockages, or abuse.

**TokenGuard** acts as a lightweight, thread-safe, and event-loop-safe middleware layer. Use it to:
*   **Evaluate Flexible Policies**: Enforce Sliding Window, Token Bucket, Fixed Window, Leaky Bucket, Cost, Quota, or Role-based policies.
*   **Prevent Cost Spikes**: Set and enforce strict token usage budgets per user, model, or session.
*   **Unify Tracking**: Track consumption across OpenAI, Groq, OpenRouter, and AWS Bedrock under a single API.
*   **Flexible Storage**: Keep track in-memory (dev) or plug in Redis, SQLite, PostgreSQL, or DynamoDB (prod) with a single config change.
*   **Proactive Alerts**: Fire warnings and webhook notifications (Slack, console) the instant thresholds are crossed.

---

<a id="architecture"></a>
## 🏗️ Architecture & Execution Flow

TokenGuard follows a modular **Strategy Pattern** architecture, cleanly decoupling token counting, policy evaluation, storage persistence, and alert dispatching into independent layers:

| Component | Responsibility | Backends / Implementations |
|---|---|---|
| **Tokenizer Layer** | Computes input and output token counts | Tiktoken (OpenAI, OpenRouter), HuggingFace (Groq), Bedrock API, Direct Payload |
| **Policy Engine** | Evaluates request rules before usage recording | Sliding Window, Token Bucket, Fixed Window, Leaky Bucket, Cost ($/day), Quota, Role |
| **Storage Layer** | Persists cumulative token totals & state | InMemory, Redis, SQLite, PostgreSQL, AWS DynamoDB |
| **Alert Manager** | Dispatches warning triggers when limits are hit | Console, Slack, Webhooks, Custom Handlers |

### Request Pipeline Flow

```mermaid
graph TD
    classDef app fill:#1e1e2e,stroke:#74c7ec,stroke-width:2px,color:#cdd6f4
    classDef core fill:#313244,stroke:#cba6f7,stroke-width:2px,color:#cdd6f4
    classDef engine fill:#45475a,stroke:#f9e2af,stroke-width:2px,color:#cdd6f4
    classDef storage fill:#313244,stroke:#a6e3a1,stroke-width:2px,color:#cdd6f4
    classDef alert fill:#313244,stroke:#f38ba8,stroke-width:2px,color:#cdd6f4
    classDef decision fill:#181825,stroke:#fab387,stroke-width:2px,color:#cdd6f4

    App["💻 Application Server"]:::app --> TG["🛡️ TokenGuard / AsyncTokenGuard"]:::core
    
    subgraph Execution Pipeline
        TG --> Counter["1. Token Counter<br/>(OpenAI, Groq, Bedrock, Direct)"]:::core
        Counter --> Policy["2. Policy Evaluator<br/>(Sliding Window, Token Bucket, Cost, Quota, Role)"]:::engine
        Policy --> Decision{"Allowed?"}:::decision
    end

    Decision -- "YES (Allowed)" --> Storage["3. Storage Backend<br/>(Memory, Redis, SQLite, Postgres, DynamoDB)"]:::storage
    Decision -- "NO (Rejected)" --> Alerts["3. Alert Manager<br/>(Console, Slack, Webhooks)"]:::alert
    
    Storage --> Result["📦 TrackResult<br/>(Cumulative Usage, Policy Metadata)"]:::core
    Alerts --> Result
    Result --> App
```

1. **Token Calculation**: TokenGuard computes exact or estimated prompt and response tokens via the configured Token Counter.
2. **Policy Evaluation**: The request context (`PolicyContext`) is passed to the Policy Engine. Active policies are evaluated in order.
3. **Decision & Execution**:
   * **Allowed**: Token usage is atomically persisted in the Storage Backend, and an approved `TrackResult` is returned.
   * **Rejected (Short-Circuit)**: Storage modification is skipped, configured Alert Handlers are triggered, and a rejected `TrackResult` (`limit_exceeded=True`) is returned with retry guidance.

---

<a id="features"></a>
## ✨ Features

| Feature | Detail |
|---|---|
| **Policy Engine** | Sliding Window, Token Bucket, Fixed Window, Leaky Bucket, Cost, Quota, Role |
| **Multi-Provider Counting** | OpenAI (exact local), Groq, OpenRouter, AWS Bedrock |
| **Exact Tracking** | `track_usage()` records exact token metrics directly from API payloads |
| **Pluggable Storage** | Seamlessly swap backends (InMemory, Redis, SQLite, PostgreSQL, DynamoDB) with one config line |
| **Budget Enforcement** | Track usage against configurable limits per `user_id` |
| **Extensible Alerts** | Console, Slack, webhooks, or custom handlers |
| **Auto-Detect Backend** | Auto-detect model tokens based on model name strings |
| **FastAPI & Async Ready** | Full async entry points and async-native database integrations |
| **Robust Test Suite** | 189 offline unit and integration tests |

---

<a id="installation"></a>
## 📦 Installation

```bash
# Core package (includes OpenAI/tiktoken local counting, policies, and memory storage)
pip install llm-token-guard

# Install optional backends & providers
pip install "llm-token-guard[redis]"         # Redis storage support
pip install "llm-token-guard[sqlite-async]"  # Async SQLite (aiosqlite) support
pip install "llm-token-guard[postgres]"      # PostgreSQL support (psycopg, asyncpg)
pip install "llm-token-guard[dynamodb]"      # AWS DynamoDB support (boto3, aioboto3)
pip install "llm-token-guard[groq]"          # Groq HuggingFace tokenizers
pip install "llm-token-guard[bedrock]"       # AWS Bedrock boto3 exact counts
pip install "llm-token-guard[all]"           # All optional dependencies
```

---

<a id="documentation-guides"></a>
## 📖 Documentation Guides

Advanced configuration, setup patterns, and code integrations are organized into individual guides:

### 1. [Policy Engine](docs/policies.md)
*   **Sliding Window**, **Token Bucket**, **Fixed Window**, and **Leaky Bucket** policy configurations.
*   **Cost Limits** ($/day), **Quota Caps** (tokens/day), and **Role-based** limit evaluation.
*   Combining multiple policies in `TokenGuard` & `AsyncTokenGuard`.
*   Extending custom policies via `BasePolicy` or `AsyncBasePolicy`.

### 2. [Token Counting & Providers](docs/providers.md)
*   **Tiktoken** exact token counts for OpenAI and OpenRouter.
*   HuggingFace tokenizer integrations for **Groq** models.
*   AWS API-driven exact counting for **AWS Bedrock**.
*   Provider accuracy comparison table.

### 3. [Storage Backends](docs/storage.md)
*   Using default `InMemoryStorage`.
*   Setting up connection pools, keys namespaces, and TTLs in `RedisStorage`.
*   Configuring persistent file storage via `SQLiteStorage`.
*   Setting up production SQL storage with **[PostgreSQL](docs/storage/postgresql.md)** (`PostgreSQLStorage` & `AsyncPostgreSQLStorage`).
*   Setting up serverless AWS storage with **[DynamoDB](docs/storage/dynamodb.md)** (`DynamoDBStorage` & `AsyncDynamoDBStorage`).
*   Initializing via **Environment Variables** or **Configuration Dictionaries**.

### 4. [FastAPI Integration](docs/fastapi.md)
*   Adding `AsyncTokenGuard` to standard web applications.
*   Managing exact API counts inside async routes without blocking.
*   Guide to API commands (`curl`) for tracking, checking, and resetting.

### 5. [Async Support](docs/async.md)
*   Writing non-blocking async codebases with `AsyncTokenGuard`.
*   Selecting async storage backends (`AsyncInMemoryStorage`, `AsyncRedisStorage`, `AsyncSQLiteStorage`, `AsyncPostgreSQLStorage`, `AsyncDynamoDBStorage`).
*   Configuring mixed sync/async alert triggers.

### 6. [Custom Backends](docs/custom-backends.md)
*   Subclassing `BaseTokenCounter` and registering with `CounterFactory`.
*   Subclassing `BaseStorage` and registering with `StorageFactory` for databases.

---

<a id="provider-compatibility"></a>
## 📊 Provider Compatibility

| Provider | Accuracy | Counting Method | Async Compatible | API Dependency |
|---|---|---|---|---|
| **OpenAI** | 100% (Exact) | Local `tiktoken` | Yes | None |
| **Groq (Default)** | ~95% | Local `tiktoken cl100k` | Yes | None |
| **Groq (Transformers)** | 100% (Exact) | Local `AutoTokenizer` | Yes | `transformers` |
| **AWS Bedrock (Local)** | ~85% - ~95% | Local estimator | Yes | None |
| **AWS Bedrock (API)** | 100% (Exact) | AWS CountTokens API | Yes | `boto3` |
| **OpenRouter** | ~85% - 100% | Local estimator | Yes | None |
| **Direct Tracking** | 100% (Exact) | `track_usage(input, output)` | Yes | None |

---

<a id="project-structure"></a>
## 🏗️ Project Structure

```
token_guard/
├── docs/                 # Detailed guides and reference docs
│   └── storage/          # Storage specific guides (PostgreSQL, DynamoDB)
├── token_guard/          # Core library source code
│   ├── counters/         # Token counters (OpenAI, Groq, Bedrock, etc.)
│   ├── engine/           # Policy evaluators and execution pipelines
│   ├── policies/         # Rate limiting, cost, quota, and role policies
│   └── storage/          # Storage backends (Memory, Redis, SQLite, Postgres, DynamoDB)
├── tests/                # Test suite (sync & async)
├── example_fastapi.py    # FastAPI integration demo
└── pyproject.toml        # Build configuration and dependencies
```

---

<a id="examples"></a>
## 🚀 Examples

Ready-to-run examples demonstrating different configuration patterns:
*   **[All-Features Demo](examples/demo_all_features.py)**: Complete runnable test suite for all sync/async features, storage drivers, and policies.
*   **[FastAPI Integration](example_fastapi.py)**: Async token limits and route handling.
*   **[Multi-Provider Demo](examples/multi_provider.py)**: Basic usage mapping different counter and storage backends.

---

<a id="running-tests"></a>
## 🧪 Running Tests

```bash
pip install -e ".[dev]"

# Run all offline sync and async tests (no API keys required)
pytest tests/ -v

# Run integration tests (requires GROQ_API_KEY env var)
export GROQ_API_KEY=gsk_...
pytest tests/test_groq_integration.py -v -s
```

---

<a id="roadmap"></a>
## 🗺️ Roadmap

- [x] Multi-provider token counting — OpenAI, Groq, OpenRouter, Bedrock ✅
- [x] Auto-detect provider — `CounterFactory.auto()` ✅
- [x] Pluggable storage — Memory, Redis, SQLite ✅
- [x] `StorageFactory` — `from_env()`, `from_url()`, `from_config()` ✅
- [x] Redis connection pooling + TTL + `from_url()` + `ping()` ✅
- [x] GitHub Actions CI/CD — auto-publish on version tag ✅
- [x] **Exact token tracking** — `track_usage()` with API-reported counts ✅
- [x] **Async support** — `async def track(...)` for async frameworks ✅
- [x] **Policy Engine (v0.5.0)** — Sliding Window, Token Bucket, Fixed Window, Leaky Bucket, Cost, Quota, Role policies ✅
- [x] **PostgreSQL & DynamoDB Storage Drivers (v0.6.0)** — Built-in enterprise storage drivers ✅
- [ ] **Budget warnings** — alert at configurable % (e.g. 80%) before hard limit
- [ ] **Prometheus metrics** — expose `token_guard_tokens_total` counter
- [ ] **Vertex AI / Cohere** — dedicated exact-count backends

---

<a id="contributing"></a>
## 🤝 Contributing

Contributions are welcome! Please follow these basic guidelines:
1. Fork the repository and create a feature branch.
2. Ensure the full test suite passes locally before submitting your PR:
   ```bash
   pytest tests/ -v
   ```
3. Follow PEP 8 style standards.

---

<a id="license"></a>
## 📄 License

MIT ©Abhijit Gunjal — see [LICENSE](LICENSE) for details.
