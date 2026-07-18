"""
counters/factory.py
--------------------
CounterFactory — creates the right BaseTokenCounter from a provider
name + model string.  This is the recommended way to instantiate a
counter when you don't want to import each backend directly.

Usage::

    counter = CounterFactory.create("openai", "gpt-4o")
    counter = CounterFactory.create("groq", "llama-3.3-70b-versatile")
    counter = CounterFactory.create("openrouter", "anthropic/claude-3-5-sonnet")
    counter = CounterFactory.create("bedrock", "meta.llama3-70b-instruct-v1:0")

    # Auto-detect from model string alone (best-effort)
    counter = CounterFactory.auto("gpt-4o")
    counter = CounterFactory.auto("anthropic.claude-3-5-sonnet-20241022-v2:0")
    counter = CounterFactory.auto("openai/gpt-4o")

Registering a custom backend::

    from token_guard.counters.base import BaseTokenCounter
    from token_guard.counters.factory import CounterFactory

    class MyCounter(BaseTokenCounter):
        @property
        def provider(self): return "myprovider"
        def count(self, text): return len(text.split())

    CounterFactory.register("myprovider", lambda model, **kw: MyCounter())

    counter = CounterFactory.create("myprovider", "my-model-v1")
"""

from __future__ import annotations
from typing import Callable, Any
from token_guard.counters.base import BaseTokenCounter


# Registry maps lowercase provider name → callable(model, **kwargs) -> BaseTokenCounter
_REGISTRY: dict[str, Callable[..., BaseTokenCounter]] = {}


def _register_defaults() -> None:
    from token_guard.counters.openai import OpenAITokenCounter
    from token_guard.counters.groq import GroqTokenCounter
    from token_guard.counters.openrouter import OpenRouterTokenCounter
    from token_guard.counters.bedrock import BedrockTokenCounter

    _REGISTRY.update({
        "openai":      lambda model, **kw: OpenAITokenCounter(model=model, **kw),
        "azure":       lambda model, **kw: OpenAITokenCounter(model=model, **kw),
        "groq":        lambda model, **kw: GroqTokenCounter(model=model, **kw),
        "openrouter":  lambda model, **kw: OpenRouterTokenCounter(model=model, **kw),
        "bedrock":     lambda model, **kw: BedrockTokenCounter(model=model, **kw),
        # Convenience aliases
        "aws":         lambda model, **kw: BedrockTokenCounter(model=model, **kw),
        "anthropic":   lambda model, **kw: OpenRouterTokenCounter(
                            model=f"anthropic/{model}", **kw),
    })


# Heuristics for CounterFactory.auto() — model string → provider
_AUTO_RULES: list[tuple[str, str]] = [
    # Bedrock IDs always contain a dot before the model slug
    ("amazon.",    "bedrock"),
    ("anthropic.", "bedrock"),
    ("meta.",      "bedrock"),
    ("mistral.",   "bedrock"),
    ("cohere.",    "bedrock"),
    ("ai21.",      "bedrock"),
    # OpenRouter IDs contain a slash
    ("openai/",    "openrouter"),
    ("anthropic/", "openrouter"),
    ("meta-llama/","openrouter"),
    ("mistralai/", "openrouter"),
    ("google/",    "openrouter"),
    ("cohere/",    "openrouter"),
    # Plain OpenAI model names
    ("gpt-",       "openai"),
    ("o1",         "openai"),
    ("o3",         "openai"),
    ("text-embedding", "openai"),
    # Groq model names
    ("llama",      "groq"),
    ("mixtral",    "groq"),
    ("gemma",      "groq"),
    ("whisper",    "groq"),
]


class CounterFactory:
    """
    Factory for creating provider-specific token counters.

    Class methods
    -------------
    create(provider, model, **kwargs)
        Explicit provider selection.
    auto(model, **kwargs)
        Best-effort provider detection from the model string.
    register(provider, factory_fn)
        Plug in a custom backend.
    list_providers()
        Show all registered provider names.
    """

    @classmethod
    def create(
        cls,
        provider: str,
        model: str,
        **kwargs: Any,
    ) -> BaseTokenCounter:
        """
        Create a counter for an explicit provider.

        Args:
            provider: Provider name (``"openai"``, ``"groq"``,
                      ``"openrouter"``, ``"bedrock"``).
            model:    Model name / ID.
            **kwargs: Forwarded to the backend constructor
                      (e.g. ``use_bedrock_api=True``).

        Raises:
            ValueError: If the provider is not registered.
        """
        if not _REGISTRY:
            _register_defaults()

        key = provider.lower()
        if key not in _REGISTRY:
            available = ", ".join(sorted(_REGISTRY))
            raise ValueError(
                f"Unknown provider '{provider}'. "
                f"Available: {available}. "
                f"Use CounterFactory.register() to add a custom backend."
            )
        return _REGISTRY[key](model, **kwargs)

    @classmethod
    def auto(cls, model: str, **kwargs: Any) -> BaseTokenCounter:
        """
        Create a counter by detecting the provider from the model string.

        Detection is heuristic — if unsure, use ``create()`` instead.

        Args:
            model:    Model name / ID.
            **kwargs: Forwarded to the backend constructor.
        """
        if not _REGISTRY:
            _register_defaults()

        model_lower = model.lower()
        for prefix, provider in _AUTO_RULES:
            if model_lower.startswith(prefix.lower()):
                return cls.create(provider, model, **kwargs)

        # Last resort: plain OpenAI counter with cl100k fallback
        from token_guard.counters.openai import OpenAITokenCounter
        return OpenAITokenCounter(model=model)

    @classmethod
    def register(
        cls,
        provider: str,
        factory_fn: Callable[..., BaseTokenCounter],
    ) -> None:
        """
        Register a custom backend.

        Args:
            provider:   Unique lowercase provider name.
            factory_fn: Callable ``(model: str, **kwargs) -> BaseTokenCounter``.

        Example::

            CounterFactory.register(
                "myprovider",
                lambda model, **kw: MyCustomCounter(model),
            )
        """
        if not _REGISTRY:
            _register_defaults()
        _REGISTRY[provider.lower()] = factory_fn

    @classmethod
    def list_providers(cls) -> list[str]:
        """Return sorted list of all registered provider names."""
        if not _REGISTRY:
            _register_defaults()
        return sorted(_REGISTRY)
