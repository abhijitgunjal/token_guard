# Async Support

`token_guard` offers first-class async/await support through `AsyncTokenGuard` and dedicated non-blocking storage backends.

---

## Basic Usage

The asynchronous API mirrors the synchronous API. Use `AsyncTokenGuard` and await tracking operations:

```python
from token_guard import AsyncTokenGuard

guard = AsyncTokenGuard(max_tokens=10_000)

async def run_chat():
    # Estimating tokens asynchronously
    result1 = await guard.track("alice", "Hello!", "Hi there!")
    
    # Tracking exact token counts asynchronously
    result2 = await guard.track_usage("alice", input_tokens=42, output_tokens=18)
    
    if result2.limit_exceeded:
         print("Budget exceeded!")
```

---

## Async Storage Backends

Always pass an async storage backend to `AsyncTokenGuard` for complete non-blocking operations:

```python
from token_guard import AsyncTokenGuard
from token_guard.storage import (
    AsyncInMemoryStorage, 
    AsyncRedisStorage, 
    AsyncSQLiteStorage
)

# 1. Async InMemory (default)
# Uses asyncio.Lock instead of threading locks
guard1 = AsyncTokenGuard(max_tokens=10_000, storage=AsyncInMemoryStorage())

# 2. Async Redis
# Uses redis.asyncio connection pools for non-blocking commands
guard2 = AsyncTokenGuard(
    max_tokens=10_000,
    storage=AsyncRedisStorage(host="localhost", port=6379, ttl=86400),
)

# 3. Async SQLite
# Uses aiosqlite for non-blocking SQL disk queries
guard3 = AsyncTokenGuard(
    max_tokens=10_000,
    storage=AsyncSQLiteStorage(path="token_usage.db"),
)
```

---

## Async Alert System

You can subclass `AsyncBaseAlertHandler` to send notifications over async networking protocols (e.g. webhooks, slack):

```python
import httpx
from token_guard import AsyncTokenGuard
from token_guard.async_alert import AsyncBaseAlertHandler
from token_guard.storage.models import UserUsage

class AsyncSlackAlertHandler(AsyncBaseAlertHandler):
    def __init__(self, url: str) -> None:
        self.url = url

    async def send(self, user_id: str, usage: UserUsage, limit: int) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(self.url, json={
                "text": f"User {user_id} is over their token budget ({usage.total_tokens}/{limit})."
            })
```

### Mixing Sync and Async Alert Handlers
`AsyncAlertManager` handles both synchronous and asynchronous handlers simultaneously. 
*   **Async handlers** are directly awaited.
*   **Sync handlers** (e.g., standard console or legacy slack handlers) are automatically offloaded to a thread executor using `asyncio.to_thread` to avoid blocking your server's event loop.

```python
from token_guard import ConsoleAlertHandler  # sync

guard = AsyncTokenGuard(
    max_tokens=5_000,
    alert_handlers=[
        ConsoleAlertHandler(),                # sync - run in thread
        AsyncSlackAlertHandler("https://..."), # async - awaited directly
    ]
)
```
