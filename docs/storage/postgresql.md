# PostgreSQL Storage Driver

TokenGuard v0.6.0 introduces native **PostgreSQL** storage drivers (`PostgreSQLStorage` and `AsyncPostgreSQLStorage`).

---

## Overview

Use PostgreSQL when your application infrastructure already runs relational databases (AWS RDS, Supabase, Neon, CockroachDB, Azure Database for PostgreSQL) and you wish to store per-user token usage without deploying a separate Redis cluster.

### Key Features
- **Atomic UPSERTs**: Implements SQL `INSERT ... ON CONFLICT (user_id) DO UPDATE` so per-user token counters are updated atomically without race conditions across multi-worker deployments.
- **Auto Table Provisioning**: Automatically creates the default `token_guard_usage` table schema on startup.
- **Sync & Async Drivers**: `PostgreSQLStorage` (sync via `psycopg`) and `AsyncPostgreSQLStorage` (async via `asyncpg`).

---

## Installation

Install optional PostgreSQL dependencies:

```bash
pip install "llm-token-guard[postgres]"
```

Or install the specific driver directly:
```bash
pip install "psycopg[binary]>=3.1.0" asyncpg
```

---

## Usage

### 1. Synchronous (`PostgreSQLStorage`)

```python
from token_guard import TokenGuard, PostgreSQLStorage, SlidingWindowPolicy

# Create from DSN URL
storage = PostgreSQLStorage.from_url("postgresql://user:password@localhost:5432/token_guard")
guard = TokenGuard(
    policy=SlidingWindowPolicy(limit=100_000, window=3600),
    storage=storage,
)

result = guard.track_usage("alice", input_tokens=450, output_tokens=120)
print(result.cumulative_usage.total_tokens)
```

### 2. Asynchronous (`AsyncPostgreSQLStorage`)

```python
import asyncio
from token_guard import AsyncTokenGuard, AsyncPostgreSQLStorage, AsyncTokenBucketPolicy

async def main():
    storage = AsyncPostgreSQLStorage.from_url("postgresql://user:password@localhost:5432/token_guard")
    guard = AsyncTokenGuard(
        policy=AsyncTokenBucketPolicy(capacity=50_000, refill_rate=500.0),
        storage=storage,
    )

    result = await guard.track_usage("bob", input_tokens=300, output_tokens=100)
    print(result.cumulative_usage.total_tokens)

asyncio.run(main())
```

### 3. Factory & Environment Variables

Create directly via `StorageFactory`:

```python
from token_guard import StorageFactory, TokenGuard

storage = StorageFactory.create("postgres", connection_string="postgresql://user:pass@localhost:5432/mydb")
guard = TokenGuard(storage=storage)
```

Or drive via environment variables:

```bash
export TOKEN_GUARD_STORAGE=postgres
export DATABASE_URL=postgresql://user:pass@localhost:5432/mydb
```

```python
from token_guard import StorageFactory, TokenGuard

guard = TokenGuard(storage=StorageFactory.from_env())
```

---

## Database Schema

`PostgreSQLStorage` auto-provisions the following schema:

```sql
CREATE TABLE IF NOT EXISTS token_guard_usage (
    user_id VARCHAR(255) PRIMARY KEY,
    input_tokens BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```
