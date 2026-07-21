# Changelog

All notable changes to llm-token-guard will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.6.1] - 2026-07-21

### Fixed & Improved
- **Resolved Event Loop Deadlock**: Fixed `PolicyEvaluator.evaluate()` deadlock when evaluating async policies inside synchronous contexts with a running event loop.
- **PostgreSQL Thread-Safety & Security**: Added `threading.Lock()` connection serialization and strict `table_name` identifier validation (`_validate_table_name`) to eliminate SQL injection vectors.
- **Policy Engine Memory Leak Eviction**: Added `max_users` capacity bounds and `_evict_expired()` key eviction routines to `FixedWindowPolicy` and `SlidingWindowPolicy`.
- **Non-Blocking Async Token Counting**: Wrapped tokenizer execution and synchronous counter calls in `asyncio.to_thread()` inside `AsyncTokenGuard.track()`.
- **Storage Latency Optimization**: Added `add_and_get_usage()` to `BaseStorage` and `AsyncBaseStorage`, reducing database network round-trips by 50%.
- **Custom Exception Hierarchy**: Added `TokenGuardError`, `ConfigurationError`, `PolicyError`, `StorageError`, and `RateLimitExceededError`.
- **Test Suite Expansion**: Added `tests/test_edge_cases.py`, increasing overall library test coverage to 86% across 219 test cases.

## [0.6.0] - 2026-07-21

### Added
- **PostgreSQL Storage Drivers**: `PostgreSQLStorage` (sync via `psycopg`) and `AsyncPostgreSQLStorage` (async via `asyncpg`) with atomic SQL `UPSERT` statements.
- **AWS DynamoDB Storage Drivers**: `DynamoDBStorage` (sync via `boto3`) and `AsyncDynamoDBStorage` (async via `aioboto3` or executor) with atomic `ADD` update expressions.
- `StorageFactory` support for `"postgres"`, `"postgresql"`, `"dynamodb"`, and `"dynamo"` string keys and environment variable resolution (`TOKEN_GUARD_STORAGE=postgres`, `TOKEN_GUARD_STORAGE=dynamodb`).
- Full Policy Engine compatibility with zero race conditions under high concurrency.
- Storage documentation guides (`docs/storage/postgresql.md` and `docs/storage/dynamodb.md`).

## [0.5.0] - 2026-07-20

### Added
- **TokenGuard Policy Engine**: Extensible policy system supporting multiple rate-limiting and budget evaluation algorithms.
- Concrete Policies: `SlidingWindowPolicy`, `TokenBucketPolicy`, `FixedWindowPolicy`, `LeakyBucketPolicy`, `CostPolicy`, `QuotaPolicy`, and `RolePolicy`.
- `PolicyEvaluator` and `AsyncPolicyEvaluator` with short-circuit evaluation.
- `PolicyFactory` for registry-driven policy resolution.
- `PolicyContext` and `PolicyResult` models.
- Policy integration in `TokenGuard` and `AsyncTokenGuard`.

## [0.4.1] - 2026-07-19

### Changed
- Refactored `README.md` into a high-level guide with a Mermaid architecture diagram and feature comparison table.
- Created `/docs` directory and moved advanced guides (`providers.md`, `storage.md`, `fastapi.md`, `async.md`, `custom-backends.md`) out of the main README.

## [0.4.0] - 2026-07-19

### Added
- Native async support via `AsyncTokenGuard`.
- Async storage backends: `AsyncInMemoryStorage`, `AsyncRedisStorage` (using `redis.asyncio`), and `AsyncSQLiteStorage` (using `aiosqlite`).
- `AsyncAlertManager` that supports mixing sync and async alert handlers.
- Updated `StorageFactory` to load and configure async backends.
- Visual banner and assets to `README.md`.
- Comprehensive unit test coverage for async flows.

### Changed
- Upgraded the FastAPI integration example (`example_fastapi.py`) to run fully asynchronous routes.

## [0.3.1] - 2026-03-22

### Added
- Documented `get_usage()`, `all_users()`, and `reset_usage()` in README.
- Renamed PyPI package name to `llm-token-guard` to avoid naming conflicts on PyPI.

## [0.3.0] - 2026-03-22

### Added
- Pluggable storage backends via `BaseStorage` ABC
  - `InMemoryStorage` — default, thread-safe, zero deps
  - `RedisStorage` — persistent, distributed, requires `pip install redis`
  - `SQLiteStorage` — persistent, zero extra deps, single-server
- `TokenGuard` now accepts a `storage=` parameter
- `TrackResult` now includes `storage_backend` field
- `TokenGuard.all_users()` method

### Changed
- `UserUsage` moved to `token_guard.storage.models` (re-exported from old location for backwards compatibility)
- `UsageTracker` is now an alias for `InMemoryStorage`
- Version bumped to `0.3.0`

---

## [0.2.0] - 2026-03-20

### Added
- Pluggable token counter backends via `BaseTokenCounter` ABC
  - `OpenAITokenCounter` — tiktoken exact counting
  - `GroqTokenCounter` — tiktoken approximation + optional HuggingFace exact counting
  - `OpenRouterTokenCounter` — tiktoken for OSS models, char-ratio for Anthropic/Cohere
  - `BedrockTokenCounter` — tiktoken for Meta/Mistral, char-ratio for Anthropic/Amazon, optional boto3 API
- `CounterFactory` with `.create()`, `.auto()`, `.register()` methods
- `TokenGuard` now accepts a `counter=` parameter
- `TrackResult` now includes `provider` field
- `TokenGuard.provider` property

### Changed
- `TokenCounter` is now an alias for `OpenAITokenCounter` (backwards compatible)
- Version bumped to `0.2.0`

---

## [0.1.0] - 2026-03-18

### Added
- Initial release
- `TokenGuard` — main public API
- `TokenCounter` — tiktoken-based token counting (OpenAI models)
- `UsageTracker` — in-memory per-user usage tracking
- `LimitManager` — configurable token limit enforcement
- `AlertManager` + `BaseAlertHandler` — extensible alert system
- `ConsoleAlertHandler` — default console alert
- FastAPI integration example
- 23 unit tests
