"""
tests/test_groq_integration.py
-------------------------------
Integration tests for GroqTokenCounter + TokenGuard with the real Groq API.

Requirements:
    pip install groq
    export GROQ_API_KEY=gsk_...

Run:
    pytest tests/test_groq_integration.py -v -s

These tests are SKIPPED automatically if GROQ_API_KEY is not set,
so they never break CI.

What this tests:
    1. track_usage() with exact API-reported token counts — always accurate
    2. GroqTokenCounter text-estimation accuracy (with overhead accounting)
    3. TokenGuard correctly tracks cumulative usage across multiple calls
    4. Limit enforcement fires when the budget is exceeded
"""

import os
import pytest

# Skip entire module if no API key is present
pytestmark = pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set — skipping Groq integration tests",
)

from groq import Groq
from token_guard import TokenGuard
from token_guard.counters import GroqTokenCounter

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

MODEL = "llama-3.3-70b-versatile"


@pytest.fixture(scope="module")
def groq_client():
    return Groq(api_key=os.environ["GROQ_API_KEY"])


@pytest.fixture(scope="module")
def guard():
    """A TokenGuard with a generous limit — no counter needed for track_usage()."""
    return TokenGuard(max_tokens=10_000)


# ---------------------------------------------------------------------------
# Helper — call Groq and return (prompt, response_text, api_usage)
# ---------------------------------------------------------------------------

def _call_groq(client: Groq, prompt: str) -> tuple[str, str, object]:
    """Make a real Groq call and return (prompt, response_text, usage)."""
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
    )
    response_text = completion.choices[0].message.content
    usage = completion.usage          # has .prompt_tokens, .completion_tokens
    return prompt, response_text, usage


# ---------------------------------------------------------------------------
# Primary tests: track_usage() with exact API-reported counts
# ---------------------------------------------------------------------------

class TestTokenGuardTrackUsageWithGroq:
    """
    End-to-end tests using track_usage() with the exact token counts
    reported by the Groq API.  These tests are always 100% accurate —
    no tolerance needed.
    """

    def test_track_usage_single_call(self, groq_client, guard):
        prompt = "What is 2 + 2?"
        _, response, usage = _call_groq(groq_client, prompt)

        result = guard.track_usage(
            user_id="exact_user",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )

        print(f"\n  provider        : {result.provider}")
        print(f"  input_tokens    : {result.input_tokens}  (API reported: {usage.prompt_tokens})")
        print(f"  output_tokens   : {result.output_tokens} (API reported: {usage.completion_tokens})")
        print(f"  limit_exceeded  : {result.limit_exceeded}")

        # Exact — no tolerance
        assert result.provider == "direct"
        assert result.input_tokens == usage.prompt_tokens
        assert result.output_tokens == usage.completion_tokens
        assert result.limit_exceeded is False

    def test_track_usage_accumulates_across_calls(self, groq_client):
        guard = TokenGuard(max_tokens=10_000)
        prompts = [
            "Name one planet.",
            "Name one color.",
            "Name one animal.",
        ]
        api_total = 0
        for prompt in prompts:
            _, _, usage = _call_groq(groq_client, prompt)
            guard.track_usage(
                "accumulate_user",
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
            )
            api_total += usage.prompt_tokens + usage.completion_tokens

        cumulative = guard.get_usage("accumulate_user").total_tokens
        assert cumulative == api_total, (
            f"Cumulative mismatch: tracked={cumulative}, api_sum={api_total}"
        )

    def test_track_usage_limit_exceeded_fires(self, groq_client):
        fired = []

        from token_guard import BaseAlertHandler
        from token_guard.tracker import UserUsage

        class CapturingHandler(BaseAlertHandler):
            def send(self, user_id: str, usage: UserUsage, limit: int) -> None:
                fired.append({"user_id": user_id, "total": usage.total_tokens})

        # A single real API response always exceeds 5 tokens
        tiny_guard = TokenGuard(
            max_tokens=5,
            alert_handlers=[CapturingHandler()],
        )

        prompt = "Say hi."
        _, _, usage = _call_groq(groq_client, prompt)
        result = tiny_guard.track_usage(
            "limit_user",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )

        assert result.limit_exceeded is True
        assert len(fired) == 1
        assert fired[0]["user_id"] == "limit_user"

    def test_track_usage_reset_clears(self, groq_client, guard):
        prompt = "What is the sun?"
        _, _, usage = _call_groq(groq_client, prompt)
        guard.track_usage(
            "reset_user",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )

        assert guard.get_usage("reset_user").total_tokens > 0
        guard.reset_usage("reset_user")
        assert guard.get_usage("reset_user").total_tokens == 0


# ---------------------------------------------------------------------------
# Secondary tests: GroqTokenCounter text-estimation accuracy
#
# These tests validate that the tiktoken estimator is a reasonable approximation
# for pre-flight use (before an API call).
#
# KNOWN LIMITATION — Groq injects a hidden default system prompt
# ("Cutting Knowledge Date / Today Date" header) for llama-3 models.
# This adds a fixed overhead (~35 tokens for llama-3.3-70b-versatile)
# to every API call.  counter.count(text) only counts raw user text;
# we cannot know what system prompt the provider injects.
#
# The tests below subtract the measured system-prompt overhead before
# comparing, so they test actual tokenizer accuracy rather than the
# provider's chat-template formatting.
# ---------------------------------------------------------------------------

class TestGroqCounterAccuracy:
    """
    Compare our tiktoken-based text estimate against Groq's API-reported counts
    (minus system-prompt overhead).  These tests validate pre-flight estimation.
    """

    @staticmethod
    def _measure_overhead(groq_client) -> int:
        """Return the number of system-prompt tokens Groq injects per call."""
        probe = "Hi"
        _, _, usage = _call_groq(groq_client, probe)
        counter = GroqTokenCounter(model=MODEL)
        return usage.prompt_tokens - counter.count(probe)

    def test_prompt_token_count_within_tolerance(self, groq_client):
        overhead = self._measure_overhead(groq_client)
        prompt = "What is the capital of France?"
        _, _, usage = _call_groq(groq_client, prompt)

        counter = GroqTokenCounter(model=MODEL)
        our_count = counter.count(prompt)
        groq_text_tokens = usage.prompt_tokens - overhead  # strip system-prompt

        print(f"\n  our count        : {our_count}")
        print(f"  groq total       : {usage.prompt_tokens}  "
              f"(overhead={overhead}, text={groq_text_tokens})")
        print(f"  diff (text only) : {abs(our_count - groq_text_tokens)}")

        tolerance = max(3, int(groq_text_tokens * 0.10))
        assert abs(our_count - groq_text_tokens) <= tolerance, (
            f"Count too far off: ours={our_count}, groq_text={groq_text_tokens} "
            f"(total={usage.prompt_tokens}, overhead={overhead})"
        )

    def test_completion_token_count_within_tolerance(self, groq_client):
        prompt = "Say exactly: Hello World"
        _, response, usage = _call_groq(groq_client, prompt)

        counter = GroqTokenCounter(model=MODEL)
        our_count = counter.count(response)
        groq_count = usage.completion_tokens

        print(f"\n  our count   : {our_count}")
        print(f"  groq actual : {groq_count}")

        tolerance = max(3, int(groq_count * 0.10))
        assert abs(our_count - groq_count) <= tolerance

    def test_longer_prompt_within_tolerance(self, groq_client):
        overhead = self._measure_overhead(groq_client)
        prompt = (
            "Explain the difference between supervised and unsupervised "
            "machine learning in two sentences."
        )
        _, _, usage = _call_groq(groq_client, prompt)

        counter = GroqTokenCounter(model=MODEL)
        our_count = counter.count(prompt)
        groq_text_tokens = usage.prompt_tokens - overhead

        print(f"\n  our count        : {our_count}")
        print(f"  groq total       : {usage.prompt_tokens}  "
              f"(overhead={overhead}, text={groq_text_tokens})")

        tolerance = max(5, int(groq_text_tokens * 0.10))
        assert abs(our_count - groq_text_tokens) <= tolerance


class TestGroqUsageReport:
    """
    Print a side-by-side accuracy report across several prompts.
    Compares: exact API counts (track_usage) vs. text estimate (counter.count).
    """

    def test_accuracy_report(self, groq_client):
        counter = GroqTokenCounter(model=MODEL)

        # Measure system-prompt overhead
        probe = "Hi"
        _, _, probe_usage = _call_groq(groq_client, probe)
        overhead = probe_usage.prompt_tokens - counter.count(probe)

        prompts = [
            "Hi",
            "What is the capital of France?",
            "Write a haiku about the ocean.",
            "Explain recursion in one sentence.",
            "List 5 programming languages.",
        ]

        print(f"\n  System-prompt overhead: {overhead} tokens")
        print(f"  {'Prompt':<45} {'Ours':>6} {'Text':>6} {'Diff':>6} {'Err%':>6}")
        print(f"  {'-'*45} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")

        for prompt in prompts:
            _, _, usage = _call_groq(groq_client, prompt)
            ours = counter.count(prompt)
            groq_text = usage.prompt_tokens - overhead  # strip system-prompt
            diff = ours - groq_text
            err = abs(diff) / groq_text * 100 if groq_text else 0
            print(f"  {prompt:<45} {ours:>6} {groq_text:>6} {diff:>+6} {err:>5.1f}%")

        # No assertion — this is a reporting test
        assert True


from groq import AsyncGroq
from token_guard import AsyncTokenGuard


@pytest.fixture(scope="module")
def async_groq_client():
    return AsyncGroq(api_key=os.environ["GROQ_API_KEY"])


@pytest.mark.asyncio
class TestAsyncTokenGuardWithGroq:
    async def test_track_usage_async(self, async_groq_client):
        guard = AsyncTokenGuard(max_tokens=10_000)

        completion = await async_groq_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Hello, how are you?"}],
            max_tokens=50,
        )
        usage = completion.usage

        result = await guard.track_usage(
            user_id="async_alice",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )

        assert result.user_id == "async_alice"
        assert result.input_tokens == usage.prompt_tokens
        assert result.output_tokens == usage.completion_tokens
        assert result.cumulative_usage.total_tokens == usage.prompt_tokens + usage.completion_tokens
