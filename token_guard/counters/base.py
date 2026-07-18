"""
counters/base.py
----------------
Abstract base class for all token counter backends.

Every backend (OpenAI/tiktoken, Groq, OpenRouter, Bedrock, …) must
subclass BaseTokenCounter and implement `count(text) -> int`.

This is the single extension point for adding new providers.
"""

import abc


class BaseTokenCounter(abc.ABC):
    """
    Abstract token counter.

    Subclass this to add support for any LLM provider.

    Minimal implementation::

        class MyCounter(BaseTokenCounter):
            @property
            def provider(self) -> str:
                return "myprovider"

            def count(self, text: str) -> int:
                # your tokenization logic here
                return len(text.split())
    """

    @property
    @abc.abstractmethod
    def provider(self) -> str:
        """Human-readable provider name, e.g. 'openai', 'groq', 'bedrock'."""

    @abc.abstractmethod
    def count(self, text: str) -> int:
        """
        Count the number of tokens in *text*.

        Args:
            text: Raw string to tokenize.

        Returns:
            Integer token count (≥ 0).
        """

    def __repr__(self) -> str:
        return f"{type(self).__name__}(provider={self.provider!r})"
