"""
tests/test_openrouter_integration.py
-------------------------------------
Integration tests for OpenRouterTokenCounter + TokenGuard with real OpenRouter API.

Requirements:
    pip install openai
    export OPENROUTER_API_KEY=sk-or-v1-...

Run:
    pytest tests/test_openrouter_integration.py -v -s

These tests are SKIPPED automatically if OPENROUTER_API_KEY is not set,
so they never break CI.

What this tests:
    1. track_usage() with exact API-reported token counts from OpenRouter
    2. OpenRouterTokenCounter text-estimation accuracy across model provider routing
    3. TokenGuard correctly tracks cumulative usage across multiple calls
    4. Limit enforcement fires when the budget is exceeded
    5. AsyncTokenGuard integration with OpenRouter API calls
"""

import os
import pytest

# Skip if openai package is not installed or OPENROUTER_API_KEY is missing
openai_module = pytest.importorskip("openai", reason="openai package not installed — skipping OpenRouter integration tests")
OpenAI = openai_module.OpenAI
AsyncOpenAI = openai_module.AsyncOpenAI

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set — skipping OpenRouter integration tests",
)

from token_guard import TokenGuard, AsyncTokenGuard
from token_guard.counters import OpenRouterTokenCounter

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "openai/gpt-4o-mini"


@pytest.fixture(scope="module")
def openrouter_client():
    return OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=OPENROUTER_BASE_URL,
    )


@pytest.fixture(scope="module")
def guard():
    """A TokenGuard with a generous limit — no counter needed for track_usage()."""
    return TokenGuard(max_tokens=10_000)


# ---------------------------------------------------------------------------
# Helper — call OpenRouter and return (prompt, response_text, api_usage)
# ---------------------------------------------------------------------------

def _call_openrouter(client: OpenAI, prompt: str, model: str = MODEL) -> tuple[str, str, object]:
    """Make a real OpenRouter call and return (prompt, response_text, usage)."""
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
    )
    response_text = completion.choices[0].message.content or ""
    usage = completion.usage          # has .prompt_tokens, .completion_tokens
    return prompt, response_text, usage


# ---------------------------------------------------------------------------
# Primary tests: track_usage() with exact API-reported counts
# ---------------------------------------------------------------------------

class TestTokenGuardTrackUsageWithOpenRouter:
    """
    End-to-end tests using track_usage() with exact token counts reported
    by OpenRouter.
    """

    def test_track_usage_single_call(self, openrouter_client, guard):
        prompt = "What is 2 + 2?"
        _, response, usage = _call_openrouter(openrouter_client, prompt)

        result = guard.track_usage(
            user_id="exact_openrouter_user",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )

        print(f"\n  provider        : {result.provider}")
        print(f"  input_tokens    : {result.input_tokens}  (API reported: {usage.prompt_tokens})")
        print(f"  output_tokens   : {result.output_tokens} (API reported: {usage.completion_tokens})")
        print(f"  limit_exceeded  : {result.limit_exceeded}")

        assert result.provider == "direct"
        assert result.input_tokens == usage.prompt_tokens
        assert result.output_tokens == usage.completion_tokens
        assert result.limit_exceeded is False

    def test_track_usage_accumulates_across_calls(self, openrouter_client):
        guard = TokenGuard(max_tokens=10_000)
        prompts = [
            "Name one planet.",
            "Name one color.",
            "Name one animal.",
        ]
        api_total = 0
        for prompt in prompts:
            _, _, usage = _call_openrouter(openrouter_client, prompt)
            guard.track_usage(
                "openrouter_accumulate_user",
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
            )
            api_total += usage.prompt_tokens + usage.completion_tokens

        cumulative = guard.get_usage("openrouter_accumulate_user").total_tokens
        assert cumulative == api_total, (
            f"Cumulative mismatch: tracked={cumulative}, api_sum={api_total}"
        )

    def test_track_usage_limit_exceeded_fires(self, openrouter_client):
        fired = []

        from token_guard import BaseAlertHandler
        from token_guard.tracker import UserUsage

        class CapturingHandler(BaseAlertHandler):
            def send(self, user_id: str, usage: UserUsage, limit: int) -> None:
                fired.append({"user_id": user_id, "total": usage.total_tokens})

        tiny_guard = TokenGuard(
            max_tokens=5,
            alert_handlers=[CapturingHandler()],
        )

        prompt = "Say hi."
        _, _, usage = _call_openrouter(openrouter_client, prompt)
        result = tiny_guard.track_usage(
            "openrouter_limit_user",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )

        assert result.limit_exceeded is True
        assert len(fired) == 1
        assert fired[0]["user_id"] == "openrouter_limit_user"

    def test_track_usage_reset_clears(self, openrouter_client, guard):
        prompt = "What is the sun?"
        _, _, usage = _call_openrouter(openrouter_client, prompt)
        guard.track_usage(
            "openrouter_reset_user",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )

        assert guard.get_usage("openrouter_reset_user").total_tokens > 0
        guard.reset_usage("openrouter_reset_user")
        assert guard.get_usage("openrouter_reset_user").total_tokens == 0


# ---------------------------------------------------------------------------
# Secondary tests: OpenRouterTokenCounter text-estimation accuracy
# ---------------------------------------------------------------------------

class TestOpenRouterCounterAccuracy:
    """
    Compare OpenRouterTokenCounter text estimation against API-reported counts.
    """

    def test_prompt_token_count_within_tolerance(self, openrouter_client):
        prompt = "What is the capital of France?"
        _, _, usage = _call_openrouter(openrouter_client, prompt)

        counter = OpenRouterTokenCounter(model=MODEL)
        our_count = counter.count(prompt)

        print(f"\n  our count        : {our_count}")
        print(f"  openrouter total : {usage.prompt_tokens}")

        tolerance = max(10, int(usage.prompt_tokens * 0.25))
        assert abs(our_count - usage.prompt_tokens) <= tolerance

    def test_completion_token_count_within_tolerance(self, openrouter_client):
        prompt = "Say exactly: Hello World"
        _, response, usage = _call_openrouter(openrouter_client, prompt)

        counter = OpenRouterTokenCounter(model=MODEL)
        our_count = counter.count(response)
        api_count = usage.completion_tokens

        print(f"\n  our count         : {our_count}")
        print(f"  openrouter actual : {api_count}")

        tolerance = max(3, int(api_count * 0.15))
        assert abs(our_count - api_count) <= tolerance


class TestOpenRouterUsageReport:
    """
    Print a side-by-side accuracy report across several prompts.
    """

    def test_accuracy_report(self, openrouter_client):
        counter = OpenRouterTokenCounter(model=MODEL)
        prompts = [
            "Hi",
            "What is the capital of France?",
            "Write a haiku about the ocean.",
            "Explain recursion in one sentence.",
            "List 5 programming languages.",
        ]

        print(f"\n  {'Prompt':<45} {'Ours':>6} {'API':>6} {'Diff':>6}")
        print(f"  {'-'*45} {'-'*6} {'-'*6} {'-'*6}")

        for prompt in prompts:
            _, _, usage = _call_openrouter(openrouter_client, prompt)
            ours = counter.count(prompt)
            api_prompt = usage.prompt_tokens
            diff = ours - api_prompt
            print(f"  {prompt:<45} {ours:>6} {api_prompt:>6} {diff:>+6}")

        assert True


@pytest.fixture(scope="module")
def async_openrouter_client():
    return AsyncOpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=OPENROUTER_BASE_URL,
    )


@pytest.mark.asyncio
class TestAsyncTokenGuardWithOpenRouter:
    async def test_track_usage_async(self, async_openrouter_client):
        guard = AsyncTokenGuard(max_tokens=10_000)

        completion = await async_openrouter_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Hello, how are you?"}],
            max_tokens=50,
        )
        usage = completion.usage

        result = await guard.track_usage(
            user_id="async_openrouter_alice",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )

        assert result.user_id == "async_openrouter_alice"
        assert result.input_tokens == usage.prompt_tokens
        assert result.output_tokens == usage.completion_tokens
        assert result.cumulative_usage.total_tokens == usage.prompt_tokens + usage.completion_tokens
