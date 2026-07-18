# Changelog

All notable changes to llm-token-guard will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
