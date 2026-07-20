# Storage Backends

Storage backends persist user token usage. You can swap storage backends seamlessly via the `StorageFactory` or by instantiating backend classes directly.

---

## Supported Backends

### In-Memory (Default)
Zero dependencies. Usage data is stored in memory and lost when the process restarts. Thread-safe using local reentrant locks.
```python
from token_guard import TokenGuard

# Uses InMemoryStorage by default
guard = TokenGuard(max_tokens=10_000)
```
Or configure explicitly:
```python
from token_guard import TokenGuard, StorageFactory

guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.create("memory"),
)
```

---

### Redis (Distributed & Production Ready)
Ideal for production setups with multiple application worker processes.
Requires: `pip install "llm-token-guard[redis]"` or `pip install redis`.

```python
from token_guard import TokenGuard, StorageFactory

# Option 1: Simple host/port
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

# Option 2: From Redis Connection URL (12-factor cloud configuration)
guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.from_url(
        "redis://:your-password@redis.myapp.com:6379/0",
        ttl=86400,
        key_prefix="myapp:tokens",
    ),
)

# Option 3: Passing your own existing redis client instance
import redis
r = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)

from token_guard.storage import RedisStorage
guard = TokenGuard(
    max_tokens=10_000,
    storage=RedisStorage(client=r, ttl=86400),
)
```

#### Redis Data Schema
Data is stored under a Redis Hash:
```
Key:    token_guard:<user_id>   (Hash)
Fields: input_tokens, output_tokens

Example:
  HGETALL token_guard:alice
  → { "input_tokens": "142", "output_tokens": "310" }
```

#### Health Check
You can ping the connection to confirm availability before bootstrap completes:
```python
from token_guard.storage import RedisStorage

store = RedisStorage(host="redis.myapp.com")
if not store.ping():
    raise RuntimeError("Redis is not reachable — check connection settings")
```

---

### SQLite (Persistent File Storage)
Persistent file-based storage. Excellent for single-instance applications. Uses Write-Ahead Logging (WAL) and atomic `UPSERT` statements.
```python
from token_guard import TokenGuard, StorageFactory

guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.create("sqlite", path="token_usage.db"),
)

# In-memory SQLite database (useful for mock environments/testing)
mock_guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.create("sqlite", path=":memory:"),
)
```

---

## Config-Driven Initialization

### Via Environment Variables
You can configure storage backends using environment variables. This avoids hardcoding keys or hosts in your source files:

```bash
# .env
TOKEN_GUARD_STORAGE=redis
REDIS_URL=redis://localhost:6379/0
TOKEN_GUARD_TTL=86400
TOKEN_GUARD_KEY_PREFIX=myapp:tokens
```

Instantiate using the factory:
```python
from token_guard import TokenGuard, StorageFactory

guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.from_env(),
)
```

---

### Via Configuration Dictionary
Useful when reading database configurations from YAML, JSON, Flask config, or Django settings.

```python
from token_guard import TokenGuard, StorageFactory

storage_config = {
    "backend": "redis",
    "url": "redis://localhost:6379/0",
    "ttl": 86400,
    "key_prefix": "myapp:tokens",
}

guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.from_config(storage_config),
)
```
