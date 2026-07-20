# Token Counting & Providers

TokenGuard supports pluggable counting backends to track or estimate token consumption. It provides built-in estimators, local exact tokenizers, and cloud API integration.

---

## Supported Providers

### OpenAI (Default)
Uses `tiktoken` — the exact same BPE tokenizer OpenAI uses internally.

```python
from token_guard import TokenGuard
from token_guard.counters import OpenAITokenCounter

guard = TokenGuard(
    max_tokens=10_000,
    counter=OpenAITokenCounter(model="gpt-4o"),  # gpt-4, gpt-3.5-turbo, etc.
)

# Estimates token counts locally via tiktoken
result = guard.track("alice", "Hello, world!", "Hi there!")
print(result.provider)  # "openai"
```

---

### Groq
Groq hosts open-source models (LLaMA, Mixtral, Gemma). By default, it uses `tiktoken cl100k_base` as a fast local approximation (~95% accurate). For exact counts, pass `use_transformers=True` (requires HuggingFace `transformers` package).

```python
from token_guard import TokenGuard
from token_guard.counters import GroqTokenCounter

# Option 1: Approximate (Default - zero extra dependencies)
guard = TokenGuard(
    max_tokens=10_000,
    counter=GroqTokenCounter(model="llama-3.3-70b-versatile"),
)

# Option 2: Exact (Requires: pip install transformers)
guard = TokenGuard(
    max_tokens=10_000,
    counter=GroqTokenCounter(
        model="llama-3.3-70b-versatile",
        use_transformers=True,
        hf_model_id="meta-llama/Meta-Llama-3-70B",  # optional HF override
    ),
)
```

Supported Groq models include: `llama-3.3-70b-versatile`, `llama-3.1-70b-versatile`, `llama-3.1-8b-instant`, `llama3-70b-8192`, `mixtral-8x7b-32768`, `gemma2-9b-it`, and more.

---

### OpenRouter
OpenRouter proxies multiple providers under one unified API. Model slugs follow the `provider/model` pattern.

```python
from token_guard import TokenGuard
from token_guard.counters import OpenRouterTokenCounter

# OpenAI models via OpenRouter (uses tiktoken exact local counting)
guard1 = TokenGuard(
    max_tokens=10_000,
    counter=OpenRouterTokenCounter("openai/gpt-4o"),
)

# Anthropic models via OpenRouter (uses character-ratio estimator, ~85% accurate)
guard2 = TokenGuard(
    max_tokens=10_000,
    counter=OpenRouterTokenCounter("anthropic/claude-3-5-sonnet"),
)

# LLaMA/Mistral via OpenRouter (uses tiktoken cl100k approximation, ~95% accurate)
guard3 = TokenGuard(
    max_tokens=10_000,
    counter=OpenRouterTokenCounter("meta-llama/llama-3.1-70b-instruct"),
)
```

---

### AWS Bedrock
Bedrock model IDs follow the `vendor.model-name` pattern.

```python
from token_guard import TokenGuard
from token_guard.counters import BedrockTokenCounter

# Option 1: Local approximation (character ratio estimator for Anthropic/Amazon)
guard1 = TokenGuard(
    max_tokens=10_000,
    counter=BedrockTokenCounter("anthropic.claude-3-5-sonnet-20241022-v2:0"),
)

# Option 2: Local tiktoken approximation for Meta LLaMA/Mistral models (~95% accurate)
guard2 = TokenGuard(
    max_tokens=10_000,
    counter=BedrockTokenCounter("meta.llama3-70b-instruct-v1:0"),
)

# Option 3: Exact remote counting (calls AWS CountTokens API — requires: pip install boto3)
guard3 = TokenGuard(
    max_tokens=10_000,
    counter=BedrockTokenCounter(
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        use_bedrock_api=True,
        aws_region="us-east-1",
    ),
)
```

---

## Auto-Detect Provider

`CounterFactory.auto()` automatically parses a model string and returns the appropriate counter configuration.

```python
from token_guard import TokenGuard
from token_guard.counters import CounterFactory

models = [
    "gpt-4o",                                      # → OpenAI
    "llama-3.3-70b-versatile",                     # → Groq
    "openai/gpt-4o",                               # → OpenRouter
    "anthropic/claude-3-5-sonnet",                 # → OpenRouter
    "anthropic.claude-3-5-sonnet-20241022-v2:0",  # → AWS Bedrock
    "meta.llama3-70b-instruct-v1:0",              # → AWS Bedrock
]

for model in models:
    counter = CounterFactory.auto(model)
    guard = TokenGuard(max_tokens=5_000, counter=counter)
    print(f"{model:<45} → {guard.provider}")
```

---

## Provider Accuracy Table

The table below illustrates the estimation method and accuracy for each counter backend when using the local `.track()` method:

| Provider | Models | Method | Accuracy |
|---|---|---|---|
| `openai` | gpt-4*, gpt-3.5-turbo*, embeddings | `tiktoken` — local | **100% (Exact)** |
| `groq` | llama-3, mixtral, gemma | `tiktoken cl100k` — local | ~95% |
| `groq` + `use_transformers=True` | any HuggingFace model | `AutoTokenizer` — local | **100% (Exact)** |
| `openrouter` | openai/*, meta-llama/*, mistral/* | `tiktoken cl100k` — local | ~95% |
| `openrouter` | anthropic/*, cohere/* | char ÷ 3.5 estimator | ~85% |
| `bedrock` | meta.*, mistral.* | `tiktoken cl100k` — local | ~95% |
| `bedrock` | anthropic.*, amazon.* | char ÷ 3.5 estimator | ~85% |
| `bedrock` + `use_bedrock_api=True` | any Bedrock model | AWS `CountTokens` API | **100% (Exact)** |
| **any provider** | — | `track_usage()` (explicit counts) | **100% (Exact)** |

> [!TIP]
> Use `track_usage()` whenever your LLM API response includes exact token counts. Use `track()` for pre-flight estimation before making an API call.
