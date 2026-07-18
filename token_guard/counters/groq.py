"""
counters/groq.py
----------------
Token counter for models served via Groq.

Each model family has its own tokenizer:

  Model family          Tokenizer                    Library
  ─────────────────     ─────────────────────────    ──────────────────────
  llama-3.*             Meta LLaMA-3 SentencePiece   HF (meta-llama/*)
  llama-2.*             Meta LLaMA-2 SentencePiece   HF (meta-llama/*)
  qwen*                 Qwen custom BPE              HF (Qwen/*)
  gpt-oss*              OpenAI BPE                   tiktoken (o200k_base)
  mixtral / mistral     Mistral SentencePiece         HF (mistralai/*)
  gemma*                Google SentencePiece          HF (google/*)
  deepseek*             LLaMA tokenizer               HF (deepseek-ai/*)
  kimi*                 Custom BPE                    HF (moonshotai/*) if avail
  whisper*              Whisper tokenizer             openai-whisper

When ``use_transformers=True`` (default), the HuggingFace ``AutoTokenizer``
is used for all HF-backed families for exact counts.  For ``gpt-oss`` models
the ``tiktoken`` library is always used regardless of this flag.

For Whisper models, token count falls back to whitespace word count because
Whisper operates on audio, not text.

Usage (approximate, no extra deps — HF families only)::

    counter = GroqTokenCounter(
        model="llama-3.3-70b-versatile",
        use_transformers=False,
    )

Usage (exact, requires ``pip install transformers``)::

    counter = GroqTokenCounter(model="llama-3.3-70b-versatile")

Usage (GPT-OSS, requires ``pip install tiktoken``)::

    counter = GroqTokenCounter(model="gpt-oss-120b")
"""

from token_guard.counters.base import BaseTokenCounter

# ---------------------------------------------------------------------------
# Model → HuggingFace repo used when use_transformers=True
# ---------------------------------------------------------------------------
_GROQ_HF_REPO: dict[str, str] = {
    # LLaMA 3.x
    "llama-3.3-70b-versatile":          "meta-llama/Meta-Llama-3-70B",
    "llama-3.1-70b-versatile":          "meta-llama/Meta-Llama-3.1-70B",
    "llama-3.1-8b-instant":             "meta-llama/Meta-Llama-3.1-8B",
    "llama3-70b-8192":                  "meta-llama/Meta-Llama-3-70B",
    "llama3-8b-8192":                   "meta-llama/Meta-Llama-3-8B",
    # LLaMA guard (uses LLaMA tokenizer)
    "llama-guard-3-8b":                 "meta-llama/Meta-Llama-Guard-3-8B",
    # Qwen
    "qwen3-32b":                        "Qwen/Qwen3-32B",
    "qwen-qwq-32b":                     "Qwen/QwQ-32B",
    # Mixtral / Mistral
    "mixtral-8x7b-32768":               "mistralai/Mixtral-8x7B-v0.1",
    # Gemma
    "gemma2-9b-it":                     "google/gemma-2-9b-it",
    "gemma-7b-it":                      "google/gemma-7b-it",
    # DeepSeek (uses LLaMA-based tokenizer, hosted under deepseek-ai)
    "deepseek-r1-distill-llama-70b":    "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
    "deepseek-r1-distill-qwen-32b":     "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
    # Kimi / Moonshot (custom BPE; fall back to cl100k_base if unavailable)
    "kimi-k2":                          "moonshotai/Kimi-K2",
}

# ---------------------------------------------------------------------------
# GPT-OSS models → tiktoken encoding (bypass HF entirely)
# ---------------------------------------------------------------------------
_GROQ_TIKTOKEN_MODELS: dict[str, str] = {
    "gpt-oss-120b":     "o200k_base",
    "gpt-oss-20b":      "o200k_base",
}

# ---------------------------------------------------------------------------
# Whisper models (audio — no meaningful text tokenizer)
# ---------------------------------------------------------------------------
_GROQ_WHISPER_MODELS = {
    "whisper-large-v3",
    "whisper-large-v3-turbo",
    "distil-whisper-large-v3-en",
}

# Tiktoken fallback encoding used when use_transformers=False for HF families
_DEFAULT_ENCODING = "cl100k_base"


class GroqTokenCounter(BaseTokenCounter):
    """
    Token counter for Groq-hosted models.

    Tokenizer selection logic
    ─────────────────────────
    1. **GPT-OSS family** — always uses ``tiktoken`` (``o200k_base``),
       regardless of ``use_transformers``.
    2. **Whisper family** — returns whitespace word count (audio models have
       no text token vocabulary).
    3. **All other families** — uses HuggingFace ``AutoTokenizer`` when
       ``use_transformers=True``; falls back to ``tiktoken`` ``cl100k_base``
       automatically if the repo is gated, ``transformers`` is not installed,
       or authentication fails (a ``RuntimeWarning`` is emitted in that case).

    Args:
        model:            Groq model name (e.g. ``"llama-3.3-70b-versatile"``).
        use_transformers: If ``True``, attempt to load the HuggingFace tokenizer
                          for exact counts.  Requires ``pip install transformers``
                          and HuggingFace authentication for gated repos
                          (``huggingface-cli login``).  Defaults to ``False``.
        hf_model_id:      Override the HuggingFace repo id.  When omitted the
                          value from the internal mapping is used, or the raw
                          model name as a last resort.
    """

    def __init__(
        self,
        model: str = "llama-3.3-70b-versatile",
        use_transformers: bool = False,
        hf_model_id: str | None = None,
    ) -> None:
        self.model = model
        self._use_transformers = use_transformers
        self._tokenizer = None      # HF tokenizer
        self._encoding = None       # tiktoken encoding
        self._is_whisper = model in _GROQ_WHISPER_MODELS

        if self._is_whisper:
            # Whisper operates on audio; we count words as a proxy.
            return

        if model in _GROQ_TIKTOKEN_MODELS:
            # GPT-OSS: always tiktoken, ignore use_transformers flag.
            import tiktoken
            self._encoding = tiktoken.get_encoding(_GROQ_TIKTOKEN_MODELS[model])
            return

        if use_transformers:
            repo = hf_model_id or _GROQ_HF_REPO.get(model, model)
            self._tokenizer = self._load_hf_tokenizer(repo)  # may set None on gated/missing
        
        if self._tokenizer is None:
            # HF unavailable (gated, no token, transformers not installed) — use tiktoken
            import tiktoken
            self._encoding = tiktoken.get_encoding(_DEFAULT_ENCODING)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_hf_tokenizer(hf_model_id: str):
        try:
            from transformers import AutoTokenizer  # type: ignore
            return AutoTokenizer.from_pretrained(hf_model_id)
        except ImportError:
            return None  # transformers not installed — caller will use tiktoken
        except OSError as e:
            import warnings
            warnings.warn(
                f"Could not load HuggingFace tokenizer for '{hf_model_id}' "
                f"({e}). "
                "Falling back to tiktoken cl100k_base approximation. "
                "To get exact counts, authenticate with HuggingFace: "
                "huggingface-cli login",
                RuntimeWarning,
                stacklevel=3,
            )
            return None

    # ------------------------------------------------------------------
    # BaseTokenCounter interface
    # ------------------------------------------------------------------

    @property
    def provider(self) -> str:
        return "groq"

    def count(self, text: str) -> int:
        if not text:
            return 0

        # Whisper: word count proxy
        if self._is_whisper:
            return len(text.split())

        # HF tokenizer (exact)
        if self._tokenizer is not None:
            return len(self._tokenizer.encode(text))

        # tiktoken (exact for GPT-OSS, approximate for others)
        return len(self._encoding.encode(text))
    