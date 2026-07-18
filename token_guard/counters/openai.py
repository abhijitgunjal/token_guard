"""
counters/openai.py
------------------
Token counter for OpenAI models (and anything that uses tiktoken).

Also works for:
  - Azure OpenAI (same models, same tokenizer)
  - Groq when serving OpenAI-compatible models (llama-3, mixtral, gemma)
    because Meta/Mistral models use the same cl100k_base / llama tokenizer
    that tiktoken can handle.

Usage::

    counter = OpenAITokenCounter(model="gpt-4o")
    counter = OpenAITokenCounter(model="gpt-3.5-turbo")
"""

import tiktoken
from token_guard.counters.base import BaseTokenCounter


class OpenAITokenCounter(BaseTokenCounter):
    """
    Tiktoken-backed counter for OpenAI (and compatible) models.

    Args:
        model: OpenAI model name used to select the correct BPE encoding.
               Falls back to ``cl100k_base`` for unrecognised model strings.
               Default: ``"gpt-4"``.

    Supported model families (tiktoken encodings):
        - gpt-4*, gpt-3.5-turbo*  → cl100k_base
        - text-embedding-ada-002   → cl100k_base
        - gpt-2 / davinci / curie  → p50k_base / r50k_base
    """

    def __init__(self, model: str = "gpt-4") -> None:
        self.model = model
        try:
            self._encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self._encoding = tiktoken.get_encoding("cl100k_base")

    @property
    def provider(self) -> str:
        return "openai"

    def count(self, text: str) -> int:
        if not text:
            return 0
        return len(self._encoding.encode(text))
