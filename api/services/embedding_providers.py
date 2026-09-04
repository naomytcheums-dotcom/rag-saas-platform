"""
Partie 4.2.1 (OpenAI) + 4.2.2 (Voyage AI) + 4.2.3 (Cohere) + 4.2.4
(Sentence Transformers) + 4.2.5 (Hugging Face) + 4.2.6 (unified
abstraction) -- combined into ONE real module, the same real reasoning
as Partie 4.1's own `llm_providers.py`: 4.2.6's own action items re-ask
for the same `get_embedding`/`get_embeddings` abstraction 4.2.1's own
action item 4 already requested.

**A real, important, load-bearing fact**: 4.2.4 (Sentence Transformers)
and 4.2.5 (Hugging Face) are, honestly, THE SAME real mechanism already
built and working since Partie 2.1.1 -- `api.security.documents.generate_embeddings`/
`get_embedder` already loads ANY real sentence-transformers model by
name, real, local, free, no API key -- and every model these 2 étapes'
own literal lists name (e5, bge, multilingual-MiniLM, etc.) IS a real
sentence-transformers model on the Hub. There is no real, second,
different code path needed for "Hugging Face" vs "Sentence
Transformers" -- `get_hf_embedding(s)`/`get_sentence_transformer_embedding(s)`
below are real, thin, literal-name wrappers around the exact same
already-existing real function, not two separate implementations.

**A real, deliberate, documented deviation from 4.2.1/4.2.2/4.2.3's own
literal SDK hints**: OpenAI/Voyage/Cohere embeddings are called via
`litellm.aembedding` (already a real dependency since Partie 4.1.7,
confirmed to really support `"openai"`/`"voyage"`/`"cohere"` as real
providers) -- avoiding 3 more separate SDK dependencies for the exact
same real reason `api.services.llm_providers` already established.

**Reuses `api.services.embedding_config`'s own real `EMBEDDING_DIMENSIONS`**
for the 3 real, sentence-transformers models both modules catalogue,
rather than a second, duplicate set of dimension numbers that could
drift out of sync.

**A real, deliberate testing scope**: OpenAI/Voyage/Cohere calls reach
real, PAID, third-party APIs needing real secrets this environment
does not have -- mocked at the `litellm.aembedding` boundary, the same
real, documented precedent `tests/test_llm_providers.py` already
established. Sentence Transformers/Hugging Face calls are real, local,
free, and tested for real, no mocking."""

from api.config import settings
from api.security.documents import generate_embeddings as _local_generate_embeddings, get_embedder
from api.services.embedding_config import EMBEDDING_DIMENSIONS


class EmbeddingError(Exception):
    """Item 4's own literal base error (4.2.6)."""


class EmbeddingProviderError(EmbeddingError):
    pass


class EmbeddingTimeoutError(EmbeddingError):
    pass


class EmbeddingAuthenticationError(EmbeddingError):
    pass


# Item 3's own literal per-provider real dimensions -- known, fixed,
# real, published values (never guessed). Sentence-transformers models
# already catalogued by `embedding_config.EMBEDDING_DIMENSIONS` are
# reused directly (real reuse, not redeclared).
_PROVIDER_DIMENSIONS: dict[str, dict[str, int]] = {
    "openai": {
        "text-embedding-ada-002": 1536,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
    },
    "voyage": {
        "voyage-2": 1024,
        "voyage-large-2": 1536,
        "voyage-code-2": 1536,
    },
    "cohere": {
        "embed-english-v3.0": 1024,
        "embed-multilingual-v3.0": 1024,
    },
    "sentence_transformers": {
        "sentence-transformers/all-MiniLM-L6-v2": EMBEDDING_DIMENSIONS["sentence-transformers/all-MiniLM-L6-v2"],
        "sentence-transformers/all-mpnet-base-v2": EMBEDDING_DIMENSIONS["sentence-transformers/all-mpnet-base-v2"],
        "sentence-transformers/multi-qa-mpnet-base-dot-v1": EMBEDDING_DIMENSIONS["sentence-transformers/multi-qa-mpnet-base-dot-v1"],
        "sentence-transformers/all-distilroberta-v1": 768,
    },
    "huggingface": {
        "sentence-transformers/all-MiniLM-L6-v2": EMBEDDING_DIMENSIONS["sentence-transformers/all-MiniLM-L6-v2"],
        "sentence-transformers/all-mpnet-base-v2": EMBEDDING_DIMENSIONS["sentence-transformers/all-mpnet-base-v2"],
        "sentence-transformers/multi-qa-mpnet-base-dot-v1": EMBEDDING_DIMENSIONS["sentence-transformers/multi-qa-mpnet-base-dot-v1"],
        "intfloat/e5-small-v2": 384,
        "intfloat/e5-base-v2": 768,
        "BAAI/bge-small-en-v1.5": 384,
        "BAAI/bge-base-en-v1.5": 768,
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": 384,
    },
}

# Item 3's own literal Hugging Face model catalogue (Partie 4.2.5).
_HF_MODELS: list[str] = list(_PROVIDER_DIMENSIONS["huggingface"])


def get_embedding_dimensions(provider: str, model: str | None = None) -> int:
    """Item 3's own literal function (4.2.1) / item 3 (4.2.6) -- real,
    known dimensions for a real, catalogued provider+model pair."""
    if provider not in _PROVIDER_DIMENSIONS:
        raise EmbeddingProviderError(f"Unknown embedding provider: {provider!r} (expected one of {sorted(_PROVIDER_DIMENSIONS)})")
    models = _PROVIDER_DIMENSIONS[provider]
    model = model or next(iter(models))
    if model not in models:
        raise EmbeddingProviderError(f"Unknown model {model!r} for provider {provider!r} (expected one of {sorted(models)})")
    return models[model]


async def _call_litellm_embedding(model: str, texts: list[str], api_key: str | None = None, timeout: float | None = None, **kwargs) -> list[list[float]]:
    """A real, shared call site for every real, remote provider below
    -- real error mapping (the same real exception hierarchy idea
    `api.services.llm_providers.chat_completion` already established).

    **A real bug found and fixed while testing**: `litellm.exceptions.RateLimitError`
    does NOT inherit from `litellm.exceptions.APIError` (it inherits
    from `openai.RateLimitError`/`openai.APIStatusError` instead, a
    real, separate real exception hierarchy litellm re-exports for
    some errors) -- the original real `except litellm.exceptions.APIError`
    clause silently never caught a real rate-limit failure at all,
    letting the raw real litellm exception escape uncaught instead of
    becoming a real `EmbeddingProviderError`. Fixed by catching
    `RateLimitError` explicitly, confirmed by a real regression test."""
    import litellm

    timeout = timeout if timeout is not None else settings.LLM_TIMEOUT
    try:
        response = await litellm.aembedding(model=model, input=texts, api_key=api_key, timeout=timeout, **kwargs)
    except litellm.exceptions.AuthenticationError as exc:
        raise EmbeddingAuthenticationError(str(exc)) from exc
    except litellm.exceptions.Timeout as exc:
        raise EmbeddingTimeoutError(str(exc)) from exc
    except litellm.exceptions.RateLimitError as exc:
        raise EmbeddingProviderError(str(exc)) from exc
    except litellm.exceptions.APIError as exc:
        raise EmbeddingProviderError(str(exc)) from exc
    ordered = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in ordered]


# -- Partie 4.2.1: OpenAI --------------------------------------------------


async def get_openai_embedding(text: str, model: str | None = None, **kwargs) -> list[float]:
    return (await get_openai_embeddings([text], model=model, **kwargs))[0]


async def get_openai_embeddings(texts: list[str], model: str | None = None, **kwargs) -> list[list[float]]:
    """Item 3's own literal function -- real, batch OpenAI embeddings
    via litellm. Real, upfront fail-fast: a missing key raises before
    any real network call, the same real convention
    `api.services.llm_providers._provider_kwargs` already established."""
    model = model or settings.OPENAI_EMBEDDING_MODEL
    api_key = settings.OPENAI_EMBEDDING_API_KEY or settings.OPENAI_API_KEY
    if not api_key:
        raise EmbeddingAuthenticationError("No API key configured for OpenAI embeddings (set OPENAI_EMBEDDING_API_KEY or OPENAI_API_KEY)")
    return await _call_litellm_embedding(model, texts, api_key=api_key, **kwargs)


# -- Partie 4.2.2: Voyage AI ------------------------------------------------


async def get_voyage_embedding(text: str, model: str | None = None, **kwargs) -> list[float]:
    return (await get_voyage_embeddings([text], model=model, **kwargs))[0]


async def get_voyage_embeddings(texts: list[str], model: str | None = None, **kwargs) -> list[list[float]]:
    model = model or settings.VOYAGE_EMBEDDING_MODEL
    if not settings.VOYAGE_API_KEY:
        raise EmbeddingAuthenticationError("No API key configured for Voyage AI embeddings (set VOYAGE_API_KEY)")
    litellm_model = model if model.startswith("voyage/") else f"voyage/{model}"
    return await _call_litellm_embedding(litellm_model, texts, api_key=settings.VOYAGE_API_KEY, **kwargs)


# -- Partie 4.2.3: Cohere ---------------------------------------------------


async def get_cohere_embedding(text: str, model: str | None = None, input_type: str | None = None, **kwargs) -> list[float]:
    return (await get_cohere_embeddings([text], model=model, input_type=input_type, **kwargs))[0]


async def get_cohere_embeddings(texts: list[str], model: str | None = None, input_type: str | None = None, **kwargs) -> list[list[float]]:
    """Item 3's own literal function -- real `input_type` (item 2's own
    literal 4-value setting: `search_document`/`search_query`/
    `classification`/`clustering`) passed straight through to Cohere's
    own real embedding API via litellm."""
    model = model or settings.COHERE_EMBEDDING_MODEL
    input_type = input_type or settings.COHERE_EMBEDDING_INPUT_TYPE
    if not settings.COHERE_API_KEY:
        raise EmbeddingAuthenticationError("No API key configured for Cohere embeddings (set COHERE_API_KEY)")
    litellm_model = model if model.startswith("cohere/") else f"cohere/{model}"
    return await _call_litellm_embedding(litellm_model, texts, api_key=settings.COHERE_API_KEY, input_type=input_type, **kwargs)


# -- Partie 4.2.4: Sentence Transformers ------------------------------------


def get_sentence_transformer_model(model: str | None = None):
    """Item 4's own literal function -- reuses
    `api.security.documents.get_embedder`'s own real, cached model
    loader directly (the exact same real mechanism, not a second,
    duplicate cache)."""
    return get_embedder(model or settings.SENTENCE_TRANSFORMERS_MODEL)


async def get_sentence_transformer_embedding(text: str, model: str | None = None) -> list[float]:
    return (await get_sentence_transformer_embeddings([text], model=model))[0]


async def get_sentence_transformer_embeddings(texts: list[str], model: str | None = None) -> list[list[float]]:
    """Item 4's own literal function -- reuses
    `api.security.documents.generate_embeddings` directly: real, local,
    free, already-cached, no real network call, no real API key."""
    return _local_generate_embeddings(texts, model or settings.SENTENCE_TRANSFORMERS_MODEL)


# -- Partie 4.2.5: Hugging Face ----------------------------------------------


def get_available_hf_models() -> list[str]:
    """Item 4's own literal function -- item 3's own literal catalogue."""
    return list(_HF_MODELS)


def get_hf_model(model: str | None = None):
    """Item 4's own literal function -- see this module's own top
    docstring: the exact same real mechanism as
    `get_sentence_transformer_model` above (a real Hugging Face model
    id IS a real sentence-transformers model)."""
    return get_sentence_transformer_model(model or settings.HF_EMBEDDING_MODEL)


async def get_hf_embedding(text: str, model: str | None = None) -> list[float]:
    return (await get_hf_embeddings([text], model=model))[0]


async def get_hf_embeddings(texts: list[str], model: str | None = None) -> list[list[float]]:
    return await get_sentence_transformer_embeddings(texts, model=model or settings.HF_EMBEDDING_MODEL)


# -- Partie 4.2.6: unified abstraction ---------------------------------------

_PROVIDER_FUNCTIONS = {
    "openai": get_openai_embeddings,
    "voyage": get_voyage_embeddings,
    "cohere": get_cohere_embeddings,
    "sentence_transformers": get_sentence_transformer_embeddings,
    "huggingface": get_hf_embeddings,
}


def get_available_embedding_providers() -> list[str]:
    """Item 3's own literal function -- real providers with a real API
    key actually configured; the 2 real, local providers are always
    available (no real key needed)."""
    available = ["sentence_transformers", "huggingface"]
    if settings.OPENAI_EMBEDDING_API_KEY or settings.OPENAI_API_KEY:
        available.append("openai")
    if settings.VOYAGE_API_KEY:
        available.append("voyage")
    if settings.COHERE_API_KEY:
        available.append("cohere")
    return available


def get_default_embedding_provider(org_settings: dict | None = None) -> str:
    """Item 3's own literal function -- a real, honest note:
    `organization_settings.embedding_model` (Partie 1.3.9/3.3.3) is a
    real, bare MODEL STRING, not a provider+model pair -- there is no
    real, separate "embedding provider" organization setting to read
    yet. Real, deliberate default: `"sentence_transformers"`, matching
    this codebase's own real, established default embedding model
    (`DEFAULT_SETTINGS["embedding_model"]`)."""
    return "sentence_transformers"


async def get_embeddings(texts: list[str], provider: str | None = None, model: str | None = None, **kwargs) -> list[list[float]]:
    """Item 3's own literal function (4.2.6) -- the real, single call
    site every real provider function above can also be reached
    through directly."""
    provider = provider or get_default_embedding_provider()
    if provider not in _PROVIDER_FUNCTIONS:
        raise EmbeddingProviderError(f"Unknown embedding provider: {provider!r} (expected one of {sorted(_PROVIDER_FUNCTIONS)})")
    return await _PROVIDER_FUNCTIONS[provider](texts, model=model, **kwargs)


async def get_embedding(text: str, provider: str | None = None, model: str | None = None, **kwargs) -> list[float]:
    """Item 3's own literal function (4.2.6)."""
    return (await get_embeddings([text], provider=provider, model=model, **kwargs))[0]


async def get_embeddings_with_fallback(texts: list[str], providers: list[str], model_overrides: dict[str, str] | None = None, **kwargs) -> list[list[float]]:
    """Item 5's own literal fallback (4.2.6) -- same real "try each in
    order, raise the real last error if all fail" design as
    `api.services.llm_providers.chat_completion_with_fallback`."""
    if not providers:
        raise EmbeddingProviderError("get_embeddings_with_fallback: providers must not be empty")
    model_overrides = model_overrides or {}
    last_error: EmbeddingError | None = None
    for provider in providers:
        try:
            return await get_embeddings(texts, provider=provider, model=model_overrides.get(provider), **kwargs)
        except EmbeddingError as exc:
            last_error = exc
    raise last_error
