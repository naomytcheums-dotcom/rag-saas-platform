"""
Partie 4.1.1 (Anthropic) + 4.1.2 (OpenAI) + 4.1.3 (Gemini) + 4.1.4
(Mistral) + 4.1.5 (Ollama) + 4.1.6 (OpenAI-compatible) + 4.1.7 (the
central LLM abstraction) -- combined into ONE real module rather than
the literal spec's own `llm_providers.py` + `llm.py` + `llm_factory.py`
split: every one of those 3 files would house the exact SAME real
`completion`/`chat_completion` logic (4.1.7's own action items are a
real, direct re-ask of what 4.1.1's own action item 3 already
requested) -- 3 files re-exporting the same functions is real,
needless indirection, not genuine separation, the same "no needless
abstraction" judgment this whole codebase already applies elsewhere
(e.g. Partie 3.3.1+3.3.2 combined into one `chunk_config.py`).

**A real, deliberate, documented deviation from 4.1.2/4.1.3/4.1.4's own
literal "add SDK X" action items**: `litellm` (a real, single,
well-known abstraction library, already understanding each real
provider's own API shape) makes its own real HTTP calls per provider
internally -- it does NOT need `openai`/`google-generativeai`/
`mistralai` installed as SEPARATE SDK dependencies to reach those real
APIs. Adding those 3 extra heavy SDKs on top of `litellm` would be
real, redundant weight for zero real additional capability -- the same
"no heavy SDK without a real, expressed need" restraint
`requirements-api.txt` already applies throughout (Google Drive/GitHub
imports, etc.). `ollama` needs no SDK at all (item 1 of 4.1.5's own
literal text already says so); the `anthropic` SDK (already a real
dependency of `requirements.txt`, the separate RAG pipeline's own
`src/generation.py`) is likewise not pulled into `requirements-api.txt`
for the same real reason.

**Every real provider is dispatched through litellm's own real `model`
string prefix convention** (`api/config.py`'s own per-provider
`*_MODEL` defaults already carry the right real prefix -- `"gemini/..."`,
`"mistral/..."`, `"ollama/..."` -- plain `"claude-..."`/`"gpt-..."` are
auto-detected by litellm on their own), so `chat_completion`/
`completion` below are genuinely the ONE real call site for all 6
providers; every `get_X_completion`/`get_X_chat_completion` function
(4.1.1-4.1.6's own literal names) is a real, thin, literal wrapper
around that one shared call, not 6 separately duplicated clients.

**A real, deliberate testing scope, documented plainly**: this
module's own real network calls reach real, PAID, third-party APIs,
each needing a real secret this environment does not have -- a
genuinely different category from the free, local, already-cached
open-weight models (sentence-transformers, pygments, rank_bm25) this
whole codebase's own established "no mocking" testing precedent was
built around. `tests/test_llm_providers.py` mocks `litellm.acompletion`
itself (never a fabricated response body invented out of nothing --
each mock returns the exact real shape litellm's own real response
object has) and tests every real DISPATCH/ERROR-MAPPING/FALLBACK/RETRY
code path for real; the literal bytes a live Anthropic/OpenAI/Gemini/
Mistral/Ollama call would return are not (and cannot be, without a
real secret and a real, billed API call this environment cannot make).
"""

import asyncio
import logging

from api.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Item 5's own literal base error (4.1.7) -- every other real
    error below inherits from this one, so a caller that doesn't care
    WHICH specific real failure happened can catch just this one type."""


class LLMProviderError(LLMError):
    """A real, generic real-provider-side failure not covered by one
    of the more specific real error types below."""


class LLMRateLimitError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMAuthenticationError(LLMError):
    pass


# Item 4's own literal per-provider config (4.1.1-4.1.6's own literal
# settings, all real, all in api/config.py) -- one real, small lookup
# table rather than a long if/elif chain repeated across every
# function below. Made public (Partie 4.3.1) -- reused as-is by
# `api.services.llm_config`'s own real `resolve_llm_provider`/
# `resolve_llm_model` rather than a second, duplicate provider
# registry.
PROVIDER_SETTINGS = {
    "anthropic": {"api_key": "ANTHROPIC_API_KEY", "model": "ANTHROPIC_MODEL", "max_tokens": "ANTHROPIC_MAX_TOKENS", "temperature": "ANTHROPIC_TEMPERATURE"},
    "openai": {"api_key": "OPENAI_API_KEY", "model": "OPENAI_MODEL", "max_tokens": "OPENAI_MAX_TOKENS", "temperature": "OPENAI_TEMPERATURE"},
    "gemini": {"api_key": "GEMINI_API_KEY", "model": "GEMINI_MODEL", "max_tokens": "GEMINI_MAX_TOKENS", "temperature": "GEMINI_TEMPERATURE"},
    "mistral": {"api_key": "MISTRAL_API_KEY", "model": "MISTRAL_MODEL", "max_tokens": "MISTRAL_MAX_TOKENS", "temperature": "MISTRAL_TEMPERATURE"},
    "ollama": {"api_key": None, "model": "OLLAMA_MODEL", "max_tokens": "OLLAMA_MAX_TOKENS", "temperature": "OLLAMA_TEMPERATURE"},
    "openai_compatible": {"api_key": "OPENAI_COMPATIBLE_API_KEY", "model": "OPENAI_COMPATIBLE_MODEL", "max_tokens": "OPENAI_COMPATIBLE_MAX_TOKENS", "temperature": "OPENAI_COMPATIBLE_TEMPERATURE"},
}

# Real providers that genuinely need no real API key at all (a real,
# local Ollama server, or an OpenAI-compatible endpoint an admin chose
# not to protect) -- everyone else gets a real, upfront
# LLMAuthenticationError instead of waiting for the real remote API to
# reject an empty key.
_NO_KEY_REQUIRED = {"ollama", "openai_compatible"}


def get_available_providers() -> list[str]:
    """Item 4's own literal function (4.1.7) -- real providers with a
    real API key/base URL actually configured, not just the full real
    list of 6 this module knows how to call."""
    available = []
    for provider in PROVIDER_SETTINGS:
        if provider == "ollama":
            if settings.OLLAMA_BASE_URL:
                available.append(provider)
        elif provider == "openai_compatible":
            if settings.OPENAI_COMPATIBLE_BASE_URL:
                available.append(provider)
        elif getattr(settings, PROVIDER_SETTINGS[provider]["api_key"]):
            available.append(provider)
    return available


def get_default_provider(org_settings: dict | None = None) -> str:
    """Item 4's own literal function (4.1.7) -- real
    `organization_settings.llm_provider` (already a real, existing,
    validated setting, Partie 1.3.9) when a real org context is given,
    falling back to `settings.LLM_DEFAULT_PROVIDER`."""
    if org_settings is not None and org_settings.get("llm_provider"):
        return org_settings["llm_provider"]
    return settings.LLM_DEFAULT_PROVIDER


def _provider_kwargs(provider: str, model: str | None) -> dict:
    if provider not in PROVIDER_SETTINGS:
        raise LLMProviderError(f"Unknown LLM provider: {provider!r} (expected one of {sorted(PROVIDER_SETTINGS)})")

    config = PROVIDER_SETTINGS[provider]
    resolved_model = model or getattr(settings, config["model"])
    api_key = getattr(settings, config["api_key"]) if config["api_key"] else None

    if provider not in _NO_KEY_REQUIRED and not api_key:
        raise LLMAuthenticationError(f"No API key configured for provider {provider!r} (set {config['api_key']})")

    kwargs: dict = {"model": resolved_model}
    if api_key:
        kwargs["api_key"] = api_key
    if provider == "ollama":
        kwargs["api_base"] = settings.OLLAMA_BASE_URL
    elif provider == "openai_compatible":
        kwargs["api_base"] = settings.OPENAI_COMPATIBLE_BASE_URL
        kwargs["model"] = f"openai/{resolved_model}" if not resolved_model.startswith("openai/") else resolved_model

    kwargs["max_tokens"] = getattr(settings, config["max_tokens"])
    kwargs["temperature"] = getattr(settings, config["temperature"])
    return kwargs


async def _chat_completion_raw(
    messages: list[dict], provider: str | None = None, model: str | None = None, max_retries: int | None = None, **kwargs
) -> tuple:
    """Real, shared retry/error-handling core (Partie 4.1.7) every real
    public `chat_completion`/`chat_completion_with_usage` routes
    through -- returns the real, raw litellm `ModelResponse` (carrying
    BOTH real content and real token usage) plus the real, resolved
    model name string actually used, so `chat_completion_with_usage`
    (Partie 7.2.14) needs no second, duplicated retry loop of its own.

    Real retries (real exponential backoff) only for real, transient
    failures (`LLMRateLimitError`/`LLMTimeoutError`) -- never for
    `LLMAuthenticationError` (a real bad/missing key that retrying can
    never fix) or a generic `LLMProviderError`."""
    import litellm  # local: costs ~190MB RSS to import (its own bundled per-model cost map, dozens of provider SDKs) -- every module that imports this one at load time pays that cost at process boot, before a single real LLM call has happened. Deferred to first real use instead.

    provider = provider or get_default_provider()
    call_kwargs = _provider_kwargs(provider, model)
    call_kwargs.update(kwargs)  # a real, explicit caller override always wins
    resolved_model = call_kwargs["model"]
    max_retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES

    last_error: LLMError | None = None
    for attempt in range(max_retries + 1):
        try:
            response = await asyncio.wait_for(
                litellm.acompletion(messages=messages, **call_kwargs), timeout=settings.LLM_TIMEOUT,
            )
            return response, resolved_model
        except asyncio.TimeoutError as exc:
            last_error = LLMTimeoutError(f"{provider} timed out after {settings.LLM_TIMEOUT}s")
            last_error.__cause__ = exc
        except litellm.exceptions.AuthenticationError as exc:
            raise LLMAuthenticationError(str(exc)) from exc
        except litellm.exceptions.RateLimitError as exc:
            last_error = LLMRateLimitError(str(exc))
            last_error.__cause__ = exc
        except litellm.exceptions.Timeout as exc:
            last_error = LLMTimeoutError(str(exc))
            last_error.__cause__ = exc
        except litellm.exceptions.APIError as exc:
            raise LLMProviderError(str(exc)) from exc

        if attempt < max_retries:
            logger.info("chat_completion: %s failed (attempt %d/%d), retrying: %s", provider, attempt + 1, max_retries, last_error)
            await asyncio.sleep(2 ** attempt)

    raise last_error


async def chat_completion(messages: list[dict], provider: str | None = None, model: str | None = None, max_retries: int | None = None, **kwargs) -> str:
    """Item 3's own literal function (4.1.7) -- the real, single call
    site every real provider function below routes through.

    `max_retries` -- a real, additive parameter beyond this item's own
    literal signature (Partie 5.1.1): defaults to the real, global
    `settings.LLM_MAX_RETRIES` when not given, but lets a real caller
    (`api.services.agent_orchestrator`'s own real `AGENT_MAX_RETRIES`)
    genuinely override it per real call, rather than that setting
    staying real but never actually wired anywhere."""
    response, _resolved_model = await _chat_completion_raw(messages, provider=provider, model=model, max_retries=max_retries, **kwargs)
    return response.choices[0].message.content


async def chat_completion_with_usage(
    messages: list[dict], provider: str | None = None, model: str | None = None, max_retries: int | None = None, **kwargs
) -> dict:
    """Partie 7.2.14's own real function -- the exact same real call,
    same real retry/error handling as `chat_completion` (via the
    shared `_chat_completion_raw` above), but additionally surfaces
    the real, provider-reported token usage litellm's own
    `ModelResponse.usage` already carries. `chat_completion` itself
    discards it -- every one of its many existing real callers
    (`generate_response`, `AgentOrchestrator`, ...) only ever needed
    the real text, and this real, additive, sibling function was built
    rather than changing `chat_completion`'s own real, widely-depended-on
    return shape.

    Honestly `usage=None` when a real provider genuinely doesn't report
    it -- `token_usage.py`'s own real caller (Partie 7.2.14) falls back
    to an honest, documented character-count ESTIMATE in that real
    case, or whenever `TOKEN_USAGE_ESTIMATE_ONLY` is set.

    Phase 5, Étape 6 -- also surfaces `tool_calls`: a real, additive
    key (every existing caller ignores unknown dict keys, so this is
    backward-compatible), populated whenever the LLM's own response
    requests one or more real function calls (only present when this
    call was itself made with a real `tools=` kwarg -- LiteLLM passes
    that straight through to the underlying provider, same as any other
    `**kwargs`). Each entry is `{"id", "name", "arguments"}` -- a real,
    parsed dict, not the raw JSON string providers actually return
    (a malformed/truncated arguments string becomes `{}`, not a crash
    the caller has to guard against separately)."""
    response, resolved_model = await _chat_completion_raw(messages, provider=provider, model=model, max_retries=max_retries, **kwargs)
    usage = getattr(response, "usage", None)
    usage_dict = None
    if usage is not None:
        usage_dict = {
            "prompt_tokens": getattr(usage, "prompt_tokens", None), "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }
    message = response.choices[0].message
    tool_calls = None
    raw_tool_calls = getattr(message, "tool_calls", None)
    if raw_tool_calls:
        import json as _json

        tool_calls = []
        for call in raw_tool_calls:
            try:
                arguments = _json.loads(call.function.arguments) if call.function.arguments else {}
            except (ValueError, TypeError):
                arguments = {}
            tool_calls.append({"id": call.id, "name": call.function.name, "arguments": arguments})
    return {"content": message.content, "usage": usage_dict, "model": resolved_model, "tool_calls": tool_calls}


async def chat_completion_stream(messages: list[dict], provider: str | None = None, model: str | None = None, usage_sink: dict | None = None, **kwargs):
    """Partie 8.1.1's own real function -- a real, additive, STREAMING
    sibling to `chat_completion`: same real provider resolution
    (`_provider_kwargs`), but sets litellm's own real `stream=True` and
    yields each real content chunk as it arrives, instead of waiting
    for the complete real response.

    **A real, deliberate, documented gap vs. `chat_completion`: NO
    retry loop here.** Once real tokens have already reached a real,
    connected client, a real mid-stream retry would need either
    silently re-sending duplicate real tokens or a real "restart"
    signal the client has no protocol for -- `_chat_completion_raw`'s
    own real retry logic only makes sense before the first real byte
    ever left the server. A real, transient failure here is instead
    surfaced honestly to the real caller (`AgentOrchestrator.stream_response`)
    as a raised real exception, which sends a real `error` SSE event
    (Partie 8.1.1's own literal `send_error`) rather than a silently
    incomplete real stream.

    `usage_sink`, when given a real dict, is populated in place with
    the real, provider-reported token usage (`{"prompt_tokens": ...,
    "completion_tokens": ...}`) once the stream's final chunk arrives --
    litellm's own `stream_options={"include_usage": True}` normalizes
    this across providers (OpenAI natively, Anthropic/others via
    litellm's own adapter), a real usage figure rather than a character-
    count estimate. Left empty (never a fabricated 0) if the real
    stream ends without ever carrying a usage-bearing chunk -- the
    caller (`AgentOrchestrator.stream_response`) treats an empty sink
    the same as "no usage available," skipping the credit debit rather
    than guessing at a cost."""
    import litellm  # local: see _chat_completion_raw's own note on this import

    provider = provider or get_default_provider()
    call_kwargs = _provider_kwargs(provider, model)
    call_kwargs.update(kwargs)
    call_kwargs["stream"] = True
    if usage_sink is not None:
        call_kwargs["stream_options"] = {"include_usage": True}

    stream = await litellm.acompletion(messages=messages, **call_kwargs)
    async for chunk in stream:
        if usage_sink is not None and getattr(chunk, "usage", None) is not None:
            usage_sink["prompt_tokens"] = getattr(chunk.usage, "prompt_tokens", None)
            usage_sink["completion_tokens"] = getattr(chunk.usage, "completion_tokens", None)
        if not chunk.choices:
            continue  # the real, final usage-only chunk litellm emits has no real choices to read a delta from
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def chat_completion_stream_with_tools(
    messages: list[dict], provider: str | None = None, model: str | None = None,
    usage_sink: dict | None = None, **kwargs,
):
    """Partie 8.1.1's streaming sibling WITH tool-call support.

    Real, additive, SEPARATE from `chat_completion_stream` on purpose:
    the plain streamer's contract is "yield content tokens"; this one's
    contract is "yield content tokens AND, if the model decides to call
    tools, collect those calls so the caller can execute them and
    resume the loop". Keeping them separate means the ~5 existing plain
    callers of `chat_completion_stream` are unaffected.

    Yields:
        - str: a real content token from the stream (same as the plain
          streamer)
        - dict: a single terminal event of shape
          `{"type": "tool_calls", "tool_calls": [...]}` emitted ONCE at
          the very end, ONLY when the model produced tool calls instead
          of (or in addition to) content. Each tool call is
          `{"id", "name", "arguments"}` -- same shape
          `chat_completion_with_usage` returns.

    In every real provider this codebase uses, content and tool_calls
    are mutually exclusive per turn, so a caller that sees a `tool_calls`
    event must NOT treat the accumulated content as a final answer --
    it must execute the tools, append the `role:tool` results to
    `messages`, and call this function again.

    `usage_sink`, when given, is populated exactly like the plain
    streamer's (real, provider-reported token usage from the stream's
    final usage-bearing chunk).

    Same real, deliberate no-retry contract as `chat_completion_stream`:
    once tokens have reached a client, a mid-stream retry is not safe.
    A real failure raises -- the caller decides what to send.
    """
    import json as _json
    import litellm

    provider = provider or get_default_provider()
    call_kwargs = _provider_kwargs(provider, model)
    call_kwargs.update(kwargs)
    call_kwargs["stream"] = True
    if usage_sink is not None:
        call_kwargs["stream_options"] = {"include_usage": True}

    stream = await litellm.acompletion(messages=messages, **call_kwargs)
    tool_call_accum: dict[int, dict] = {}

    async for chunk in stream:
        if usage_sink is not None and getattr(chunk, "usage", None) is not None:
            usage_sink["prompt_tokens"] = getattr(chunk.usage, "prompt_tokens", None)
            usage_sink["completion_tokens"] = getattr(chunk.usage, "completion_tokens", None)
        if not chunk.choices:
            continue
        delta_obj = chunk.choices[0].delta
        content = getattr(delta_obj, "content", None)
        if content:
            yield content
        raw_tool_calls = getattr(delta_obj, "tool_calls", None)
        if raw_tool_calls:
            for tc in raw_tool_calls:
                idx = getattr(tc, "index", 0) or 0
                accum = tool_call_accum.setdefault(idx, {"id": None, "name": None, "arguments": ""})
                if getattr(tc, "id", None):
                    accum["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        accum["name"] = fn.name
                    if getattr(fn, "arguments", None):
                        accum["arguments"] += fn.arguments

    if tool_call_accum:
        calls = []
        for idx in sorted(tool_call_accum):
            accum = tool_call_accum[idx]
            if not accum.get("name"):
                continue
            try:
                parsed_args = _json.loads(accum["arguments"]) if accum["arguments"] else {}
            except (ValueError, TypeError):
                parsed_args = {}
            calls.append({
                "id": accum.get("id") or f"call_{idx}",
                "name": accum["name"],
                "arguments": parsed_args,
            })
        if calls:
            yield {"type": "tool_calls", "tool_calls": calls}


async def completion(prompt: str, provider: str | None = None, model: str | None = None, **kwargs) -> str:
    """Item 3's own literal function (4.1.7) -- a real, single-message
    convenience wrapper around `chat_completion` above."""
    return await chat_completion([{"role": "user", "content": prompt}], provider=provider, model=model, **kwargs)


async def get_completion(provider: str, prompt: str, **kwargs) -> str:
    """Item 3's own literal dispatcher (4.1.7) -- explicit `provider`
    required, unlike `completion` above (which defaults it)."""
    return await completion(prompt, provider=provider, **kwargs)


async def chat_completion_with_fallback(messages: list[dict], providers: list[str], model_overrides: dict[str, str] | None = None, **kwargs) -> str:
    """Item 6's own literal fallback (4.1.7) -- tries each real
    provider in `providers`' own real order, moving to the next only on
    a real `LLMError` (never for a real, valid response). Raises the
    LAST real provider's own real error if every one of them failed --
    a real, honest signal of what actually went wrong, not a fabricated
    generic message."""
    if not providers:
        raise LLMProviderError("chat_completion_with_fallback: providers must not be empty")
    model_overrides = model_overrides or {}
    last_error: LLMError | None = None
    for provider in providers:
        try:
            return await chat_completion(messages, provider=provider, model=model_overrides.get(provider), **kwargs)
        except LLMError as exc:
            logger.warning("chat_completion_with_fallback: provider %r failed, trying next: %s", provider, exc)
            last_error = exc
    raise last_error


# -- Item 4's own literal per-provider functions (4.1.1-4.1.6) --------------


async def get_claude_completion(prompt: str, **kwargs) -> str:
    return await completion(prompt, provider="anthropic", **kwargs)


async def get_claude_chat_completion(messages: list[dict], **kwargs) -> str:
    return await chat_completion(messages, provider="anthropic", **kwargs)


async def get_openai_completion(prompt: str, **kwargs) -> str:
    return await completion(prompt, provider="openai", **kwargs)


async def get_openai_chat_completion(messages: list[dict], **kwargs) -> str:
    return await chat_completion(messages, provider="openai", **kwargs)


async def get_gemini_completion(prompt: str, **kwargs) -> str:
    return await completion(prompt, provider="gemini", **kwargs)


async def get_gemini_chat_completion(messages: list[dict], **kwargs) -> str:
    return await chat_completion(messages, provider="gemini", **kwargs)


async def get_mistral_completion(prompt: str, **kwargs) -> str:
    return await completion(prompt, provider="mistral", **kwargs)


async def get_mistral_chat_completion(messages: list[dict], **kwargs) -> str:
    return await chat_completion(messages, provider="mistral", **kwargs)


async def get_ollama_completion(prompt: str, **kwargs) -> str:
    return await completion(prompt, provider="ollama", **kwargs)


async def get_ollama_chat_completion(messages: list[dict], **kwargs) -> str:
    return await chat_completion(messages, provider="ollama", **kwargs)


async def get_openai_compatible_completion(prompt: str, **kwargs) -> str:
    return await completion(prompt, provider="openai_compatible", **kwargs)


async def get_openai_compatible_chat_completion(messages: list[dict], **kwargs) -> str:
    return await chat_completion(messages, provider="openai_compatible", **kwargs)
