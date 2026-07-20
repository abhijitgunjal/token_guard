# FastAPI Integration

`token_guard` is fully ready for asynchronous web frameworks. This guide demonstrates how to integrate `AsyncTokenGuard` into a FastAPI application for non-blocking token tracking, limits, and alerts.

---

## Installation & Setup

Install FastAPI and Uvicorn server along with `token_guard`'s FastAPI extras:
```bash
pip install "llm-token-guard[fastapi]"
```

Start the interactive server reload loop:
```bash
# Run the demo app directly from source folder
cd token_guard
uvicorn example_fastapi:app --reload
```

Interactive OpenAPI Swagger UI is automatically available at:
`http://127.0.0.1:8000/docs`

---

## FastAPI Integration Pattern

Here is the standard implementation pattern to integrate `AsyncTokenGuard` into your existing FastAPI backend:

```python
from fastapi import FastAPI, HTTPException
from token_guard import AsyncTokenGuard, StorageFactory
from token_guard.counters import CounterFactory

app = FastAPI()

# 1. Initialize once at startup (using environment variable storage configuration)
guard = AsyncTokenGuard(
    max_tokens=10_000,
    counter=CounterFactory.auto("gpt-4o"),
    storage=StorageFactory.from_env(),  # driven by TOKEN_GUARD_STORAGE env var
)

@app.post("/chat")
async def chat(user_id: str, prompt: str):
    # 2. Call your LLM backend
    response = await call_llm(prompt)

    # 3. Track actual usage reported by the provider's API (100% accurate, non-blocking)
    result = await guard.track_usage(
        user_id=user_id,
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
    )

    # Alternatively, estimate before or without the LLM response:
    # result = await guard.track(user_id=user_id, input_text=prompt, output_text=response)

    # 4. Enforce limits
    if result.limit_exceeded:
        raise HTTPException(
            status_code=429, 
            detail=f"Token limit exceeded. Current budget: {result.limit} tokens."
        )

    return {"response": response, "tokens_used": result.total_tokens}
```

---

## API Commands Guide

Use `curl` or any API client to test endpoints:

### Track Tokens
Select a provider and submit texts to estimate usage and verify limits:
```bash
curl -X POST "http://127.0.0.1:8000/chat?provider=openai&max_tokens=5000" \
     -H "Content-Type: application/json" \
     -d '{"user_id": "alice", "prompt": "What is Python?", "response": "Python is a programming language."}'
```
Response:
```json
{
  "user_id": "alice",
  "provider": "openai",
  "model": "gpt-4o",
  "input_tokens": 5,
  "output_tokens": 6,
  "request_total_tokens": 11,
  "cumulative_total_tokens": 11,
  "limit": 5000,
  "limit_exceeded": false,
  "utilization_pct": 0.22
}
```

### Check Usage
Verify cumulative consumption for a user ID:
```bash
curl "http://127.0.0.1:8000/usage/alice?provider=openai"
```

### Reset usage
Clear usage limits to start a new billing window:
```bash
curl -X DELETE "http://127.0.0.1:8000/usage/alice?provider=openai"
```
