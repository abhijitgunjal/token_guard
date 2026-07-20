# Custom Backends

TokenGuard's core design makes it easy to integrate custom token counters and storage backends.

---

## Custom Token Counters

To support a custom model tokenizer or external counter API, subclass `BaseTokenCounter` and implement the `provider` property and `count()` method:

```python
from token_guard import TokenGuard
from token_guard.counters import BaseTokenCounter, CounterFactory

class CustomVertexCounter(BaseTokenCounter):
    @property
    def provider(self) -> str:
        return "vertexai"

    def count(self, text: str) -> int:
        # Example using the google-genai or vertexai package
        import vertexai
        from vertexai.generative_models import GenerativeModel
        
        model = GenerativeModel("gemini-1.5-pro")
        return model.count_tokens(text).total_tokens
```

### Registering and Using Custom Counters
Register the counter factory callable with `CounterFactory` during application startup:

```python
# Register the factory mapping
CounterFactory.register("vertexai", lambda model, **kw: CustomVertexCounter())

# Resolve and instantiate anywhere in the app
guard = TokenGuard(
    max_tokens=10_000,
    counter=CounterFactory.create("vertexai", model="gemini-1.5-pro"),
)
```

---

## Custom Storage Backends

To persist token usage data in a custom data store (like PostgreSQL, DynamoDB, MongoDB), subclass `BaseStorage` and implement the four abstract methods:

```python
from token_guard import TokenGuard
from token_guard.storage import BaseStorage, StorageFactory
from token_guard.storage.models import UserUsage

class PostgresStorage(BaseStorage):
    def __init__(self, dsn: str) -> None:
        import psycopg2
        self._conn = psycopg2.connect(dsn)
        
        # Initialize table
        with self._conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    user_id TEXT PRIMARY KEY,
                    input_tokens INT DEFAULT 0,
                    output_tokens INT DEFAULT 0
                )
            """)
        self._conn.commit()

    def add_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> None:
        with self._conn.cursor() as cur:
            cur.execute("""
                INSERT INTO token_usage (user_id, input_tokens, output_tokens)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    input_tokens = token_usage.input_tokens + EXCLUDED.input_tokens,
                    output_tokens = token_usage.output_tokens + EXCLUDED.output_tokens
            """, (user_id, input_tokens, output_tokens))
        self._conn.commit()

    def get_usage(self, user_id: str) -> UserUsage:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT input_tokens, output_tokens FROM token_usage WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()
        if not row:
            return UserUsage()
        return UserUsage(input_tokens=row[0], output_tokens=row[1])

    def reset_usage(self, user_id: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM token_usage WHERE user_id = %s", (user_id,))
        self._conn.commit()

    def all_users(self) -> dict[str, UserUsage]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT user_id, input_tokens, output_tokens FROM token_usage")
            rows = cur.fetchall()
        return {r[0]: UserUsage(input_tokens=r[1], output_tokens=r[2]) for r in rows}
```

### Registering and Using Custom Storage
Register the factory mapping with `StorageFactory`:

```python
# Register the backend
StorageFactory.register("postgres", lambda **kw: PostgresStorage(**kw))

# Instantiate via factory
guard = TokenGuard(
    max_tokens=10_000,
    storage=StorageFactory.create("postgres", dsn="postgresql://localhost/mydb"),
)
```
