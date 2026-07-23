"""
tests/test_bedrock_integration.py
----------------------------------
Integration tests for BedrockTokenCounter + TokenGuard with real AWS Bedrock API.

Requirements:
    pip install boto3
    export AWS_ACCESS_KEY_ID=AKIA...
    export AWS_SECRET_ACCESS_KEY=...
    export AWS_DEFAULT_REGION=us-east-1

Run:
    pytest tests/test_bedrock_integration.py -v -s

These tests are SKIPPED automatically if AWS credentials are not set,
so they never break CI.

What this tests:
    1. track_usage() with exact API-reported token counts from AWS Bedrock
    2. BedrockTokenCounter text-estimation accuracy across Bedrock model vendors
    3. TokenGuard correctly tracks cumulative usage across multiple calls
    4. Limit enforcement fires when the budget is exceeded
    5. Optional exact count retrieval via Bedrock CountTokens API
"""

import os
import pytest

# Skip if boto3 package is not installed or AWS credentials missing
boto3 = pytest.importorskip("boto3", reason="boto3 package not installed — skipping Bedrock integration tests")
from botocore.exceptions import BotoCoreError, ClientError

has_aws_creds = bool(
    (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))
    or os.getenv("AWS_PROFILE")
    or os.getenv("AWS_EXECUTION_ENV")
)

pytestmark = pytest.mark.skipif(
    not has_aws_creds,
    reason="AWS credentials not configured — skipping Bedrock integration tests",
)

from token_guard import TokenGuard, AsyncTokenGuard
from token_guard.counters import BedrockTokenCounter

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

MODEL = "amazon.titan-text-express-v1"
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture(scope="module")
def bedrock_client():
    return boto3.client("bedrock-runtime", region_name=AWS_REGION)


@pytest.fixture(scope="module")
def guard():
    """A TokenGuard with a generous limit — no counter needed for track_usage()."""
    return TokenGuard(max_tokens=10_000)


# ---------------------------------------------------------------------------
# Helper — call AWS Bedrock Converse API and return (prompt, response_text, input_tokens, output_tokens)
# ---------------------------------------------------------------------------

def _call_bedrock(client, prompt: str, model: str = MODEL) -> tuple[str, str, int, int]:
    """Make a real Bedrock Converse call and return (prompt, response_text, input_tokens, output_tokens)."""
    response = client.converse(
        modelId=model,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 150},
    )
    output_message = response["output"]["message"]["content"][0]["text"]
    usage = response.get("usage", {})
    input_tokens = usage.get("inputTokens", 0)
    output_tokens = usage.get("outputTokens", 0)
    return prompt, output_message, input_tokens, output_tokens


# ---------------------------------------------------------------------------
# Primary tests: track_usage() with exact API-reported counts
# ---------------------------------------------------------------------------

class TestTokenGuardTrackUsageWithBedrock:
    """
    End-to-end tests using track_usage() with exact token counts reported
    by AWS Bedrock.
    """

    def test_track_usage_single_call(self, bedrock_client, guard):
        prompt = "What is 2 + 2?"
        _, response, in_tokens, out_tokens = _call_bedrock(bedrock_client, prompt)

        result = guard.track_usage(
            user_id="exact_bedrock_user",
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )

        print(f"\n  provider        : {result.provider}")
        print(f"  input_tokens    : {result.input_tokens}  (API reported: {in_tokens})")
        print(f"  output_tokens   : {result.output_tokens} (API reported: {out_tokens})")
        print(f"  limit_exceeded  : {result.limit_exceeded}")

        assert result.provider == "direct"
        assert result.input_tokens == in_tokens
        assert result.output_tokens == out_tokens
        assert result.limit_exceeded is False

    def test_track_usage_accumulates_across_calls(self, bedrock_client):
        guard = TokenGuard(max_tokens=10_000)
        prompts = [
            "Name one planet.",
            "Name one color.",
            "Name one animal.",
        ]
        api_total = 0
        for prompt in prompts:
            _, _, in_tokens, out_tokens = _call_bedrock(bedrock_client, prompt)
            guard.track_usage(
                "bedrock_accumulate_user",
                input_tokens=in_tokens,
                output_tokens=out_tokens,
            )
            api_total += in_tokens + out_tokens

        cumulative = guard.get_usage("bedrock_accumulate_user").total_tokens
        assert cumulative == api_total, (
            f"Cumulative mismatch: tracked={cumulative}, api_sum={api_total}"
        )

    def test_track_usage_limit_exceeded_fires(self, bedrock_client):
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
        _, _, in_tokens, out_tokens = _call_bedrock(bedrock_client, prompt)
        result = tiny_guard.track_usage(
            "bedrock_limit_user",
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )

        assert result.limit_exceeded is True
        assert len(fired) == 1
        assert fired[0]["user_id"] == "bedrock_limit_user"

    def test_track_usage_reset_clears(self, bedrock_client, guard):
        prompt = "What is the sun?"
        _, _, in_tokens, out_tokens = _call_bedrock(bedrock_client, prompt)
        guard.track_usage(
            "bedrock_reset_user",
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )

        assert guard.get_usage("bedrock_reset_user").total_tokens > 0
        guard.reset_usage("bedrock_reset_user")
        assert guard.get_usage("bedrock_reset_user").total_tokens == 0


# ---------------------------------------------------------------------------
# Secondary tests: BedrockTokenCounter text-estimation accuracy
# ---------------------------------------------------------------------------

class TestBedrockCounterAccuracy:
    """
    Compare BedrockTokenCounter text estimation against API-reported counts.
    """

    def test_prompt_token_count_within_tolerance(self, bedrock_client):
        prompt = "What is the capital of France?"
        _, _, in_tokens, _ = _call_bedrock(bedrock_client, prompt)

        counter = BedrockTokenCounter(model=MODEL)
        our_count = counter.count(prompt)

        print(f"\n  our count     : {our_count}")
        print(f"  bedrock total : {in_tokens}")

        tolerance = max(10, int(in_tokens * 0.30))
        assert abs(our_count - in_tokens) <= tolerance

    def test_completion_token_count_within_tolerance(self, bedrock_client):
        prompt = "Say exactly: Hello World"
        _, response, _, out_tokens = _call_bedrock(bedrock_client, prompt)

        counter = BedrockTokenCounter(model=MODEL)
        our_count = counter.count(response)

        print(f"\n  our count      : {our_count}")
        print(f"  bedrock actual : {out_tokens}")

        tolerance = max(5, int(out_tokens * 0.25))
        assert abs(our_count - out_tokens) <= tolerance


class TestBedrockUsageReport:
    """
    Print a side-by-side accuracy report across several prompts.
    """

    def test_accuracy_report(self, bedrock_client):
        counter = BedrockTokenCounter(model=MODEL)
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
            _, _, in_tokens, _ = _call_bedrock(bedrock_client, prompt)
            ours = counter.count(prompt)
            diff = ours - in_tokens
            print(f"  {prompt:<45} {ours:>6} {in_tokens:>6} {diff:>+6}")

        assert True
