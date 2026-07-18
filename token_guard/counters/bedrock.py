"""
counters/bedrock.py
--------------------
Token counter for models served via AWS Bedrock.

Bedrock hosts models from multiple providers under one API.
Model IDs follow AWS ARN-like patterns:

    amazon.titan-text-express-v1
    amazon.nova-pro-v1:0
    anthropic.claude-3-5-sonnet-20241022-v2:0
    meta.llama3-70b-instruct-v1:0
    mistral.mixtral-8x7b-instruct-v0:1
    cohere.command-r-plus-v1:0
    ai21.jamba-instruct-v1:0

Strategy
--------
Parse the vendor prefix (everything before the first ``"."``) and route
to the most accurate available tokenizer.

Accuracy table:
    Vendor prefix   Method                  Accuracy
    ─────────────   ───────────────────────  ────────
    amazon          char ÷ 4.0 estimate      ~80 %  (Titan/Nova — no public tokenizer)
    anthropic       char ÷ 3.5 estimate      ~85 %  (Claude — no public tokenizer)
    meta            tiktoken cl100k          ~95 %  (LLaMA models)
    mistral         tiktoken cl100k          ~95 %  (Mistral/Mixtral)
    cohere          char ÷ 4.0 estimate      ~80 %  (Command-R)
    ai21            char ÷ 4.0 estimate      ~80 %  (Jamba)
    *  (unknown)    word count               ~75 %

Optional exact counting
-----------------------
For Amazon/Anthropic models you can call the Bedrock ``CountTokens`` API
directly (requires boto3 and IAM permissions).  Pass
``use_bedrock_api=True`` to enable this.

    counter = BedrockTokenCounter(
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        use_bedrock_api=True,
        aws_region="us-east-1",
    )

Usage (approximate, zero extra deps)::

    counter = BedrockTokenCounter(model="anthropic.claude-3-5-sonnet-20241022-v2:0")
    counter = BedrockTokenCounter(model="meta.llama3-70b-instruct-v1:0")
"""

from __future__ import annotations
import math
from token_guard.counters.base import BaseTokenCounter


_VENDOR_TO_ENCODING: dict[str, str | None] = {
    "amazon":    None,   # Titan / Nova — no public tokenizer
    "anthropic": None,   # Claude — no public tokenizer
    "meta":      "cl100k_base",
    "mistral":   "cl100k_base",
    "cohere":    None,
    "ai21":      None,
    "stability": None,   # image models — token count = 0 makes no sense
}

_CHARS_PER_TOKEN: dict[str, float] = {
    "anthropic": 3.5,
    "amazon":    4.0,
    "cohere":    4.0,
    "ai21":      4.0,
}
_DEFAULT_CHARS_PER_TOKEN = 4.0


def _vendor(model_id: str) -> str:
    """Extract vendor prefix from Bedrock model ID."""
    return model_id.split(".")[0].lower()


class BedrockTokenCounter(BaseTokenCounter):
    """
    Token counter for AWS Bedrock models.

    Args:
        model:            Bedrock model ID,
                          e.g. ``"anthropic.claude-3-5-sonnet-20241022-v2:0"``.
        use_bedrock_api:  If ``True``, call the Bedrock ``CountTokens`` API for
                          exact counts.  Requires ``boto3`` and IAM permissions.
        aws_region:       AWS region for the Bedrock API call
                          (default: ``"us-east-1"``).
    """

    def __init__(
        self,
        model: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        use_bedrock_api: bool = False,
        aws_region: str = "us-east-1",
    ) -> None:
        self.model = model
        self._vendor = _vendor(model)
        self._use_bedrock_api = use_bedrock_api
        self._aws_region = aws_region
        self._encoding = None
        self._chars_per_token: float | None = None
        self._bedrock_client = None

        if use_bedrock_api:
            self._bedrock_client = self._make_client(aws_region)
        else:
            enc_name = _VENDOR_TO_ENCODING.get(self._vendor)
            if enc_name is not None:
                import tiktoken
                self._encoding = tiktoken.get_encoding(enc_name)
            else:
                self._chars_per_token = _CHARS_PER_TOKEN.get(
                    self._vendor, _DEFAULT_CHARS_PER_TOKEN
                )

    @staticmethod
    def _make_client(region: str):
        try:
            import boto3  # type: ignore
            return boto3.client("bedrock-runtime", region_name=region)
        except ImportError as e:
            raise ImportError(
                "Install boto3 to use the Bedrock CountTokens API: "
                "pip install boto3"
            ) from e

    @property
    def provider(self) -> str:
        return "bedrock"

    @property
    def counting_method(self) -> str:
        if self._use_bedrock_api:
            return "bedrock_api"
        if self._encoding is not None:
            return "tiktoken"
        return "estimator"

    def count(self, text: str) -> int:
        if not text:
            return 0

        if self._use_bedrock_api and self._bedrock_client is not None:
            return self._count_via_api(text)

        if self._encoding is not None:
            return len(self._encoding.encode(text))

        return math.ceil(len(text) / self._chars_per_token)  # type: ignore[arg-type]

    def _count_via_api(self, text: str) -> int:
        """
        Call the Bedrock CountTokens API.
        Docs: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_CountTokens.html
        """
        try:
            response = self._bedrock_client.count_tokens(
                modelId=self.model,
                textPrompt=text,
            )
            return response.get("tokenCount", 0)
        except Exception as exc:  # noqa: BLE001
            # If the API call fails, fall back to estimator so we never crash
            import logging
            logging.getLogger(__name__).warning(
                "Bedrock CountTokens API failed (%s), falling back to estimator.", exc
            )
            return math.ceil(len(text) / _DEFAULT_CHARS_PER_TOKEN)
