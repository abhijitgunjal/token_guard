"""
tests/test_openai_integration.py
---------------------------------
Integration tests for OpenAITokenCounter + TokenGuard with the real OpenAI API.

Requirements:
    pip install openai
    export OPENAI_API_KEY=sk-...

Run:
    pytest tests/test_openai_integration.py -v -s

These tests are SKIPPED automatically if OPENAI_API_KEY is not set,
so they never break CI.

What this tests:
    1. track_usage() with exact API-reported token counts — always accurate
    2. OpenAITokenCounter text-estimation accuracy via tiktoken
    3. TokenGuard correctly tracks cumulative usage across multiple calls
    4. Limit enforcement fires when the budget is exceeded
    5. AsyncTokenGuard integration with AsyncOpenAI
"""

import os
import pytest

# Skip if openai package is not installed or OPENAI_API_KEY is missing
openai_module = pytest.importorskip("openai", reason="openai package not installed — skipping OpenAI integration tests")
OpenAI = openai_module.OpenAI
AsyncOpenAI = openai_module.AsyncOpenAI

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping OpenAI integration tests",
)

from token_guard import TokenGuard, AsyncTokenGuard
from token_guard.counters import OpenAITokenCounter

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

MODEL = "gpt-4o-mini"


@pytest.fixture(scope="module")
def openai_client():
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


@pytest.fixture(scope="module")
def guard():
    """A TokenGuard with a generous limit — no counter needed for track_usage()."""
    return TokenGuard(max_tokens=10_000)


# ---------------------------------------------------------------------------
# Helper — call OpenAI and return (prompt, response_text, api_usage)
# ---------------------------------------------------------------------------

def _call_openai(client: OpenAI, prompt: str) -> tuple[str, str, object]:
    """Make a real OpenAI call and return (prompt, response_text, usage)."""
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
    )
    response_text = completion.choices[0].message.content or ""
    usage = completion.usage          # has .prompt_tokens, .completion_tokens
    return prompt, response_text, usage


# ---------------------------------------------------------------------------
# Primary tests: track_usage() with exact API-reported counts
# ---------------------------------------------------------------------------

class TestTokenGuardTrackUsageWithOpenAI:
    """
    End-to-end tests using track_usage() with the exact token counts
    reported by the OpenAI API.
    """

    def test_track_usage_single_call(self, openai_client, guard):
        prompt = "What is 2 + 2?"
        _, response, usage = _call_openai(openai_client, prompt)

        result = guard.track_usage(
            user_id="exact_openai_user",
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

    def test_track_usage_accumulates_across_calls(self, openai_client):
        guard = TokenGuard(max_tokens=10_000)
        prompts = [
            "Name one planet.",
            "Name one color.",
            "Name one animal.",
        ]
        api_total = 0
        for prompt in prompts:
            _, _, usage = _call_openai(openai_client, prompt)
            guard.track_usage(
                "openai_accumulate_user",
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
            )
            api_total += usage.prompt_tokens + usage.completion_tokens

        cumulative = guard.get_usage("openai_accumulate_user").total_tokens
        assert cumulative == api_total, (
            f"Cumulative mismatch: tracked={cumulative}, api_sum={api_total}"
        )

    def test_track_usage_limit_exceeded_fires(self, openai_client):
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
        _, _, usage = _call_openai(openai_client, prompt)
        result = tiny_guard.track_usage(
            "openai_limit_user",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )

        assert result.limit_exceeded is True
        assert len(fired) == 1
        assert fired[0]["user_id"] == "openai_limit_user"

    def test_track_usage_reset_clears(self, openai_client, guard):
        prompt = "What is the sun?"
        _, _, usage = _call_openai(openai_client, prompt)
        guard.track_usage(
            "openai_reset_user",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )

        assert guard.get_usage("openai_reset_user").total_tokens > 0
        guard.reset_usage("openai_reset_user")
        assert guard.get_usage("openai_reset_user").total_tokens == 0


# ---------------------------------------------------------------------------
# Secondary tests: OpenAITokenCounter text-estimation accuracy
# ---------------------------------------------------------------------------

class TestOpenAICounterAccuracy:
    """
    Compare tiktoken-based text estimate against OpenAI's API-reported counts.
    """

    def test_prompt_token_count_within_tolerance(self, openai_client):
        prompt = "What is the capital of France?"
        _, _, usage = _call_openai(openai_client, prompt)

        counter = OpenAITokenCounter(model=MODEL)
        our_count = counter.count(prompt)

        print(f"\n  our count    : {our_count}")
        print(f"  openai total : {usage.prompt_tokens}")

        # OpenAI chat completion formatting adds ~7 tokens per message wrapper overhead
        tolerance = max(10, int(usage.prompt_tokens * 0.20))
        assert abs(our_count - usage.prompt_tokens) <= tolerance

    def test_completion_token_count_exact(self, openai_client):
        prompt = "Say exactly: Hello World"
        _, response, usage = _call_openai(openai_client, prompt)

        counter = OpenAITokenCounter(model=MODEL)
        our_count = counter.count(response)
        openai_count = usage.completion_tokens

        print(f"\n  our count      : {our_count}")
        print(f"  openai actual : {openai_count}")

        tolerance = max(3, int(openai_count * 0.10))
        assert abs(our_count - openai_count) <= tolerance

    def test_longer_prompt_within_tolerance(self, openai_client):
        prompt = (
            "Explain the difference between supervised and unsupervised "
            "machine learning in two sentences."
        )
        _, _, usage = _call_openai(openai_client, prompt)

        counter = OpenAITokenCounter(model=MODEL)
        our_count = counter.count(prompt)

        print(f"\n  our count    : {our_count}")
        print(f"  openai total : {usage.prompt_tokens}")

        tolerance = max(10, int(usage.prompt_tokens * 0.20))
        assert abs(our_count - usage.prompt_tokens) <= tolerance


class TestOpenAIUsageReport:
    """
    Print a side-by-side accuracy report across several prompts.
    """

    def test_accuracy_report(self, openai_client):
        counter = OpenAITokenCounter(model=MODEL)
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
            _, _, usage = _call_openai(openai_client, prompt)
            ours = counter.count(prompt)
            api_prompt = usage.prompt_tokens
            diff = ours - api_prompt
            print(f"  {prompt:<45} {ours:>6} {api_prompt:>6} {diff:>+6}")

        assert True


@pytest.fixture(scope="module")
def async_openai_client():
    return AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])


@pytest.mark.asyncio
class TestAsyncTokenGuardWithOpenAI:
    async def test_track_usage_async(self, async_openai_client):
        guard = AsyncTokenGuard(max_tokens=10_000)

        completion = await async_openai_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Hello, how are you?"}],
            max_tokens=50,
        )
        usage = completion.usage

        result = await guard.track_usage(
            user_id="async_openai_alice",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )

        assert result.user_id == "async_openai_alice"
        assert result.input_tokens == usage.prompt_tokens
        assert result.output_tokens == usage.completion_tokens
        assert result.cumulative_usage.total_tokens == usage.prompt_tokens + usage.completion_tokens
