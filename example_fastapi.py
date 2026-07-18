"""
example_fastapi.py
------------------
FastAPI integration with multi-provider TokenGuard support.

Run with:
    pip install -e ".[fastapi]"
    uvicorn example_fastapi:app --reload

Provider is selected per-request via a query param:
    POST /chat?provider=openai
    POST /chat?provider=groq
    POST /chat?provider=openrouter
    POST /chat?provider=bedrock
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from token_guard import TokenGuard, TrackResult
from token_guard.counters import (
    CounterFactory,
    OpenAITokenCounter,
    GroqTokenCounter,
    OpenRouterTokenCounter,
    BedrockTokenCounter,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TokenGuard Multi-Provider Demo",
    description="LLM token tracking across OpenAI, Groq, OpenRouter, and Bedrock.",
    version="0.3.1",
)

# One guard per provider — each has its own counter and shared tracker
# In production these would be singletons from config / dependency injection
_GUARDS: dict[str, TokenGuard] = {}


def _get_guard(provider: str, model: str, max_tokens: int = 5_000) -> TokenGuard:
    """Return (or create) a TokenGuard for the given provider+model pair."""
    key = f"{provider}:{model}"
    if key not in _GUARDS:
        counter = CounterFactory.create(provider, model)
        _GUARDS[key] = TokenGuard(max_tokens=max_tokens, counter=counter)
    return _GUARDS[key]


# ---------------------------------------------------------------------------
# Default guards (shown in /providers endpoint)
# ---------------------------------------------------------------------------

_DEFAULT_MODELS: dict[str, str] = {
    "openai":      "gpt-4o",
    "groq":        "llama-3.3-70b-versatile",
    "openrouter":  "openai/gpt-4o",
    "bedrock":     "anthropic.claude-3-5-sonnet-20241022-v2:0",
}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    user_id: str
    prompt: str
    response: str
    model: str | None = None   # override model for this request


class ChatExactRequest(BaseModel):
    """Request body for /chat/exact — pass exact API-reported token counts."""
    user_id: str
    input_tokens: int
    output_tokens: int


class ChatResponse(BaseModel):
    user_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    request_total_tokens: int
    cumulative_total_tokens: int
    limit: int
    limit_exceeded: bool
    utilization_pct: float


class UsageResponse(BaseModel):
    user_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    provider: str = Query(default="openai", description="openai | groq | openrouter | bedrock"),
    max_tokens: int = Query(default=5_000, description="Token limit for this user"),
) -> ChatResponse:
    """Track tokens for an LLM exchange. Provider is selected via ?provider=."""
    if provider not in _DEFAULT_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{provider}'. "
                   f"Supported: {list(_DEFAULT_MODELS)}",
        )

    model = body.model or _DEFAULT_MODELS[provider]
    guard = _get_guard(provider, model, max_tokens)
    result: TrackResult = guard.track(
        user_id=body.user_id,
        input_text=body.prompt,
        output_text=body.response,
    )

    if result.limit_exceeded:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Token limit exceeded",
                "user_id": result.user_id,
                "provider": provider,
                "cumulative_total_tokens": result.cumulative_usage.total_tokens,
                "limit": result.limit,
            },
        )

    return ChatResponse(
        user_id=result.user_id,
        provider=result.provider,
        model=model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        request_total_tokens=result.total_tokens,
        cumulative_total_tokens=result.cumulative_usage.total_tokens,
        limit=result.limit,
        limit_exceeded=result.limit_exceeded,
        utilization_pct=round(result.utilization * 100, 2),
    )


@app.post("/chat/exact", response_model=ChatResponse)
def chat_exact(
    body: ChatExactRequest,
    provider: str = Query(default="openai", description="openai | groq | openrouter | bedrock"),
    max_tokens: int = Query(default=5_000, description="Token limit for this user"),
) -> ChatResponse:
    """
    Track token usage using **exact counts** from the LLM API response.

    Pass ``input_tokens`` and ``output_tokens`` directly from the provider's
    usage object (e.g. ``usage.prompt_tokens``, ``usage.completion_tokens``).
    This is the recommended endpoint for production — always 100% accurate.
    """
    if body.input_tokens < 0 or body.output_tokens < 0:
        raise HTTPException(
            status_code=422,
            detail="input_tokens and output_tokens must be >= 0",
        )

    model = _DEFAULT_MODELS.get(provider, "unknown")
    guard = _get_guard(provider, model, max_tokens)
    result: TrackResult = guard.track_usage(
        user_id=body.user_id,
        input_tokens=body.input_tokens,
        output_tokens=body.output_tokens,
    )

    if result.limit_exceeded:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Token limit exceeded",
                "user_id": result.user_id,
                "provider": provider,
                "cumulative_total_tokens": result.cumulative_usage.total_tokens,
                "limit": result.limit,
            },
        )

    return ChatResponse(
        user_id=result.user_id,
        provider=provider,
        model=model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        request_total_tokens=result.total_tokens,
        cumulative_total_tokens=result.cumulative_usage.total_tokens,
        limit=result.limit,
        limit_exceeded=result.limit_exceeded,
        utilization_pct=round(result.utilization * 100, 2),
    )


@app.get("/usage/{user_id}", response_model=UsageResponse)
def get_usage(
    user_id: str,
    provider: str = Query(default="openai"),
    model: str | None = Query(default=None),
) -> UsageResponse:
    """Return cumulative token usage for a user on a given provider."""
    resolved_model = model or _DEFAULT_MODELS.get(provider, "gpt-4o")
    guard = _get_guard(provider, resolved_model)
    usage = guard.get_usage(user_id)
    return UsageResponse(
        user_id=user_id,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
    )


@app.delete("/usage/{user_id}")
def reset_usage(
    user_id: str,
    provider: str = Query(default="openai"),
    model: str | None = Query(default=None),
) -> dict:
    """Reset the token usage counter for a user on a given provider."""
    resolved_model = model or _DEFAULT_MODELS.get(provider, "gpt-4o")
    guard = _get_guard(provider, resolved_model)
    guard.reset_usage(user_id)
    return {"message": f"Usage reset for user='{user_id}' provider='{provider}'"}


@app.get("/providers")
def list_providers() -> dict:
    """List all registered counter providers and their default models."""
    from token_guard.counters import CounterFactory
    return {
        "registered_providers": CounterFactory.list_providers(),
        "default_models": _DEFAULT_MODELS,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.3.1"}
