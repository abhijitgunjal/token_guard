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
## Quick Start

### 1. Direct Token Tracking & Policy Enforcement

Track exact token usage reported by LLM API responses and enforce rate-limiting policies:

```python
from token_guard import TokenGuard, SlidingWindowPolicy

# Configure a Sliding Window Policy: max 50,000 tokens per hour
policy = SlidingWindowPolicy(limit=50_000, window=3600)
guard = TokenGuard(policy=policy)

# Record exact token usage for a user request
result = guard.track_usage("user_123", input_tokens=420, output_tokens=150)

print(result.total_tokens)                    # 570
print(result.limit_exceeded)                  # False
print(result.cumulative_usage.total_tokens)   # 570
```

### 2. Async Tracking for Web Frameworks (FastAPI / Starlette)

Use non-blocking async execution in web servers:

```python
import asyncio
from token_guard import AsyncTokenGuard, AsyncTokenBucketPolicy

async def main():
    policy = AsyncTokenBucketPolicy(capacity=10_000, refill_rate=100.0)
    guard = AsyncTokenGuard(policy=policy)
    
    result = await guard.track_usage("user_456", input_tokens=80, output_tokens=20)
    print(result.total_tokens)   # 100
    print(result.limit_exceeded) # False

asyncio.run(main())
```

---

<a id="why-token-guard"></a>
## Why TokenGuard?

LLM API calls are billed per token (inputs + outputs). Uncontrolled application requests can quickly trigger unexpected cost spikes, upstream rate limit errors, or user abuse.

**TokenGuard** operates as a lightweight, thread-safe, and event-loop-safe middleware layer:

* **Flexible Policy Engine**: Enforce Sliding Window, Token Bucket, Fixed Window, Leaky Bucket, Cost ($/day), Quota, or Role-based rate limits.
* **Cost & Budget Protection**: Enforce usage caps per user, model, tier, or session.
* **Unified Multi-Provider Support**: Track token metrics across OpenAI, Groq, OpenRouter, and AWS Bedrock under a single unified API.
* **Pluggable Enterprise Storage**: Keep state in-memory during development or swap to Redis, SQLite, PostgreSQL, or AWS DynamoDB in production with one config change.
* **Real-time Alerts**: Dispatch warnings and webhook notifications (Slack, console, webhooks) the moment limit thresholds are crossed.

---

<a id="features"></a>
## Features

| Feature | Description |
|---|---|
| **Policy Engine** | Enforce Sliding Window, Token Bucket, Fixed Window, Leaky Bucket, Cost, Quota, and Role-based policies |
| **Multi-Provider Counting** | Exact tiktoken tokenizers (OpenAI, OpenRouter), HuggingFace (Groq), and AWS Bedrock APIs |
| **Exact Tracking** | `track_usage()` records exact token metrics directly from LLM API payloads |
| **Pluggable Storage** | Seamlessly swap backends (InMemory, Redis, SQLite, PostgreSQL, AWS DynamoDB) via config |
| **Budget & Limit Control** | Track cumulative usage against configurable limits per `user_id` |
| **Extensible Alerts** | Dispatch limit-exceeded warnings to Console, Slack, webhooks, or custom handlers |
| **Auto-Detect Backend** | Automatically map models to tokenizers via `CounterFactory.auto()` |
| **FastAPI & Async Ready** | Fully non-blocking async entry points (`AsyncTokenGuard`) and async database drivers |
| **Robust Test Suite** | 219 offline unit and integration tests |

---

<a id="installation"></a>
## Installation

```bash
# Core package (includes OpenAI/tiktoken local counting, policies, and memory storage)
pip install llm-token-guard

# Install optional storage backends & provider extras:
pip install "llm-token-guard[redis]"         # Redis storage support
pip install "llm-token-guard[postgres]"      # PostgreSQL support (psycopg, asyncpg)
pip install "llm-token-guard[dynamodb]"      # AWS DynamoDB support (boto3, aioboto3)
pip install "llm-token-guard[sqlite-async]"  # Async SQLite (aiosqlite) support
pip install "llm-token-guard[groq]"          # Groq HuggingFace tokenizers
pip install "llm-token-guard[bedrock]"       # AWS Bedrock CountTokens API
pip install "llm-token-guard[all]"           # All optional dependencies
```

---

<a id="code-examples"></a>
## Essential Usage Examples

### 1. Combining Multiple Policies

Combine rate limits, daily cost caps, and monthly quotas into a single `TokenGuard` instance:

```python
from token_guard import TokenGuard, SlidingWindowPolicy, CostPolicy, QuotaPolicy

policies = [
    SlidingWindowPolicy(limit=10_000, window=3600),     # Max 10k tokens / hour
    CostPolicy(daily_limit_usd=5.0),                    # Max $5.00 cost / day
    QuotaPolicy(monthly_tokens=500_000),                # Max 500k tokens / month
]

guard = TokenGuard(policies=policies)
result = guard.track_usage("user_789", input_tokens=500, output_tokens=200)

if result.limit_exceeded:
    print(f"Request blocked: {result.policy_result.reason}")
    print(f"Retry after: {result.policy_result.retry_after}s")
```

### 2. Configuring Production Storage Backends

Initialize storage backends using `StorageFactory` or environment variables:

```python
from token_guard import TokenGuard, StorageFactory, SlidingWindowPolicy

# Option A: Create storage from a DSN connection string (Postgres / Redis / SQLite)
storage = StorageFactory.create("postgres", connection_string="postgresql://user:pass@localhost:5432/db")

# Option B: Auto-create storage from environment variables (e.g. TOKEN_GUARD_STORAGE=redis)
# storage = StorageFactory.from_env()

guard = TokenGuard(
    policy=SlidingWindowPolicy(limit=50_000, window=3600),
    storage=storage,
)
```

### 3. Text Token Counting & Auto Provider Detection

Count tokens from text strings before executing LLM requests:

```python
from token_guard import TokenGuard, CounterFactory

# Auto-detect token counter based on model name
counter = CounterFactory.auto("meta-llama/llama-3-70b-instruct")
guard = TokenGuard(counter=counter)

# Track usage from prompt and response text
result = guard.track(
    user_id="user_123",
    input_text="Explain quantum computing in simple terms.",
    output_text="Quantum computing is a field of computing focused on quantum physics principles..."
)

print(f"Input Tokens: {result.input_tokens}")
print(f"Output Tokens: {result.output_tokens}")
```

### 4. Setting Up Alert Handlers

Trigger warning alerts when users breach limits:

```python
from token_guard import TokenGuard, BaseAlertHandler

class SlackWebhookAlertHandler(BaseAlertHandler):
    def alert(self, user_id: str, usage, max_tokens: int) -> None:
        print(f"[ALERT] User {user_id} exceeded token limit! Usage: {usage.total_tokens}")

guard = TokenGuard(
    max_tokens=1_000,
    alert_handlers=[SlackWebhookAlertHandler()]
)
```

---

<a id="architecture"></a>
## Architecture & Execution Pipeline

TokenGuard follows a modular **Strategy Pattern** architecture, cleanly decoupling token counting, policy evaluation, storage persistence, and alert dispatching into independent layers:

| Component | Responsibility | Implementations |
|---|---|---|
| **Tokenizer Layer** | Computes input and output token counts | Tiktoken (OpenAI, OpenRouter), HuggingFace (Groq), Bedrock API, Direct Payload |
| **Policy Engine** | Evaluates request rules before usage recording | Sliding Window, Token Bucket, Fixed Window, Leaky Bucket, Cost ($/day), Quota, Role |
| **Storage Layer** | Persists cumulative token totals & state | InMemory, Redis, SQLite, PostgreSQL, AWS DynamoDB |
| **Alert Manager** | Dispatches warning triggers when limits are hit | Console, Slack, Webhooks, Custom Handlers |

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

<a id="provider-compatibility"></a>
## Provider Compatibility

| Provider | Accuracy | Counting Method | Async Compatible | Dependency |
|---|---|---|---|---|
| **OpenAI** | 100% (Exact) | Local `tiktoken` | Yes | None |
| **Groq (Default)** | ~95% | Local `tiktoken cl100k` | Yes | None |
| **Groq (Transformers)** | 100% (Exact) | Local `AutoTokenizer` | Yes | `transformers` |
| **AWS Bedrock (Local)** | ~85% - ~95% | Local estimator | Yes | None |
| **AWS Bedrock (API)** | 100% (Exact) | AWS CountTokens API | Yes | `boto3` |
| **OpenRouter** | ~85% - 100% | Local estimator | Yes | None |
| **Direct Tracking** | 100% (Exact) | `track_usage(input, output)` | Yes | None |

---

<a id="documentation-guides"></a>
## Documentation & Advanced Guides

For detailed setup instructions, configuration options, and advanced integrations, refer to the documentation guides:

* 📘 **[Policy Engine Guide](docs/policies.md)** — In-depth configurations for Sliding Window, Token Bucket, Cost, Quota, and Role-based policies.
* 📘 **[Token Counting & Providers Guide](docs/providers.md)** — Tokenizer selection and accuracy comparisons for OpenAI, Groq, OpenRouter, and AWS Bedrock.
* 📘 **[Storage Backends Guide](docs/storage.md)** — Production setup for Redis, SQLite, PostgreSQL, and AWS DynamoDB.
  * 📘 **[PostgreSQL Setup Guide](docs/storage/postgresql.md)** — Sync (`psycopg`) & Async (`asyncpg`) PostgreSQL storage setup.
  * 📘 **[AWS DynamoDB Setup Guide](docs/storage/dynamodb.md)** — Serverless AWS DynamoDB storage setup.
* 📘 **[FastAPI Integration Guide](docs/fastapi.md)** — Adding `AsyncTokenGuard` middleware and non-blocking route tracking.
* 📘 **[Async Support Guide](docs/async.md)** — Event loop integration and async storage drivers.
* 📘 **[Custom Backends Guide](docs/custom-backends.md)** — Implementing custom counters, storage drivers, and policies.

---

<a id="project-structure"></a>
## Project Structure

```
token_guard/
├── docs/                 # Detailed guides and reference docs
│   └── storage/          # Storage-specific guides (PostgreSQL, DynamoDB)
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
## Runnable Examples

* **[All-Features Demo](examples/demo_all_features.py)**: Runnable test suite demonstrating sync/async features, storage drivers, and policies.
* **[FastAPI Integration Demo](example_fastapi.py)**: Web server integration with async token limits and route handling.
* **[Multi-Provider Demo](examples/multi_provider.py)**: Mapping multiple counter and storage backends.

---

<a id="running-tests"></a>
## Running Tests

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
## Roadmap

### Completed Milestones
- [x] **Multi-provider token counting** — OpenAI, Groq, OpenRouter, AWS Bedrock ✅
- [x] **Auto-detect provider** — `CounterFactory.auto()` ✅
- [x] **Pluggable storage** — Memory, Redis, SQLite ✅
- [x] **StorageFactory** — `from_env()`, `from_url()`, `from_config()` ✅
- [x] **Redis connection pooling** + TTL + `from_url()` + `ping()` ✅
- [x] **GitHub Actions CI/CD** — auto-publish on version tag ✅
- [x] **Exact token tracking** — `track_usage()` with API-reported counts ✅
- [x] **Async support** — `async def track(...)` for non-blocking execution ✅
- [x] **Policy Engine (v0.5.0)** — Sliding Window, Token Bucket, Fixed Window, Leaky Bucket, Cost, Quota, Role policies ✅
- [x] **PostgreSQL & DynamoDB Drivers (v0.6.0)** — Built-in enterprise storage drivers ✅
- [x] **Hardening & Performance (v0.6.1)** — Deadlock fixes, thread safety, memory eviction, double query optimization, custom exceptions ✅

### Upcoming Enterprise Roadmap

#### Phase 1: Distributed Storage-Backed Policies
- [ ] **Redis Lua & SQL Window Counters** — Execute rate-limiting counters directly in storage (Redis Lua scripts & Postgres SQL window queries) for cluster-wide rate limiting across pod workers.
- [ ] **Budget Warning Thresholds** — Fire warning alerts at configurable percentages (e.g. 80%) before hard limit rejection.

#### Phase 2: Enterprise Middleware & Webhook Handlers
- [ ] **FastAPI & Starlette Middleware** — Native drop-in `TokenGuardMiddleware` with automatic API key extraction, policy enforcement, and standardized HTTP 429 JSON responses with `Retry-After` headers.
- [ ] **Enterprise Alert Handlers** — Built-in `SlackAlertHandler`, `WebhookAlertHandler`, and `PagerDutyAlertHandler`.

#### Phase 3: Observability & Provider Expansion
- [ ] **Prometheus Metrics Exporter** — Expose `token_guard_tokens_total` counters and `token_guard_policy_rejections_total` histograms.
- [ ] **OpenTelemetry Tracing** — Automatic trace spans across counter calculation and policy evaluation.
- [ ] **Vertex AI & Cohere Counters** — Native exact token counting backends.

---

<a id="contributing"></a>
## Contributing

Contributions are welcome! Please follow these basic guidelines:
1. Fork the repository and create a feature branch.
2. Ensure the full test suite passes locally before submitting your PR:
   ```bash
   pytest tests/ -v
   ```
3. Follow PEP 8 style standards.

---

<a id="license"></a>
## License

MIT ©Abhijit Gunjal — see [LICENSE](LICENSE) for details.
