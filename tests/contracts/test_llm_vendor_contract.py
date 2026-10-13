"""Specs 4.1.1 Anthropic, 4.1.2 OpenAI, 4.1.3 Gemini, 4.1.4 Mistral -- CONTRACT tests against LOCAL FAKE servers.

What is real here: the product code (api/services/llm_providers.py) and LiteLLM's HTTP client, over a real loopback socket.
What is fake: the vendor. tests/vendor_fakes.FakeVendor speaks the wire format of each vendor (path, auth header, JSON/SSE shapes, error bodies).
This does NOT prove that a real account works -> scripts/validate_llm_live.py (guarded by RUN_LIVE_VENDOR_VALIDATION=1) is the real check.
"""

import json

import pytest

from api.config import settings
from api.services import llm_providers
from api.services.llm_providers import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    chat_completion,
    chat_completion_stream,
    chat_completion_with_fallback,
    chat_completion_with_usage,
)
from vendor_fakes import FakeVendor, Resp

MESSAGES = [{"role": "system", "content": "Be brief."}, {"role": "user", "content": "Say pong"}]


def anthropic_ok(text="pong"):
    return Resp(200, {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-x", "content": [{"type": "text", "text": text}],
                      "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 11, "output_tokens": 3}})


def openai_ok(text="pong", model="gpt-x"):
    return Resp(200, {"id": "chatcmpl-1", "object": "chat.completion", "created": 1, "model": model,
                      "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                      "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14}})


def gemini_ok(text="pong"):
    return Resp(200, {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP", "index": 0}],
                      "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 3, "totalTokenCount": 14}})


# provider -> (settings key, route, ok-response factory, header carrying the key, header value, auth-error body)
VENDORS = {
    "anthropic": ("ANTHROPIC_API_KEY", "/v1/messages", anthropic_ok, "x-api-key", lambda k: k,
                  {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}),
    "openai": ("OPENAI_API_KEY", "/chat/completions", openai_ok, "authorization", lambda k: f"Bearer {k}",
               {"error": {"message": "Incorrect API key provided", "type": "invalid_request_error", "code": "invalid_api_key"}}),
    "gemini": ("GEMINI_API_KEY", "/models/*", gemini_ok, "x-goog-api-key", lambda k: k,
               {"error": {"code": 401, "message": "API key not valid. Please pass a valid API key.", "status": "UNAUTHENTICATED"}}),
    "mistral": ("MISTRAL_API_KEY", "/v1/chat/completions", openai_ok, "authorization", lambda k: f"Bearer {k}",
                {"message": "Unauthorized", "request_id": "r1"}),
}


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    for provider, (key_setting, *_rest) in VENDORS.items():
        monkeypatch.setattr(settings, key_setting, f"contract-test-key-{provider}")
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(settings, "LLM_TIMEOUT", 20)

    async def no_sleep(_):  # the product's exponential back-off is not what is under test
        return None

    monkeypatch.setattr(llm_providers.asyncio, "sleep", no_sleep)


@pytest.fixture
def fake():
    with FakeVendor() as f:
        yield f


def route(fake: FakeVendor, provider: str, response):
    fake.on("POST", VENDORS[provider][1], response)


@pytest.mark.parametrize("provider", list(VENDORS))
async def test_request_shape_auth_header_and_parsed_answer(fake, provider):
    _key_setting, _path, ok, header, header_value, _err = VENDORS[provider]
    route(fake, provider, ok("pong"))
    result = await chat_completion_with_usage(MESSAGES, provider=provider, api_base=fake.url, max_retries=0)
    assert result["content"] == "pong"
    assert result["usage"]["prompt_tokens"] == 11 and result["usage"]["completion_tokens"] == 3
    (request,) = fake.requests
    assert request.headers[header] == header_value(f"contract-test-key-{provider}")  # the product setting, in the vendor's own header
    body = request.json()
    if provider == "gemini":
        assert any(part.get("text") == "Say pong" for c in body["contents"] for part in c["parts"])
        assert "Be brief." in json.dumps(body["system_instruction"])
        assert body["generationConfig"]["max_output_tokens"] == settings.GEMINI_MAX_TOKENS
    else:
        assert body["max_tokens"] == getattr(settings, f"{provider.upper()}_MAX_TOKENS")
        text = json.dumps(body)
        assert "Say pong" in text and "Be brief." in text
    if provider == "anthropic":
        assert request.headers["anthropic-version"]
        assert body["system"] and body["messages"][0]["role"] == "user"  # Anthropic keeps the system prompt out of `messages`
    if provider in ("openai", "mistral"):
        assert body["messages"][0] == {"role": "system", "content": "Be brief."}


@pytest.mark.parametrize("provider", list(VENDORS))
async def test_authentication_error_is_mapped_and_never_retried(fake, provider):
    route(fake, provider, Resp(401, VENDORS[provider][5]))
    with pytest.raises(LLMAuthenticationError):
        await chat_completion(MESSAGES, provider=provider, api_base=fake.url, max_retries=3)
    assert len(fake.requests) == 1


@pytest.mark.parametrize("provider", list(VENDORS))
async def test_rate_limit_is_retried_then_succeeds(fake, provider):
    limited = Resp(429, {"error": {"message": "Rate limit reached", "type": "rate_limit_error", "code": "rate_limit_exceeded"}}, headers={"retry-after": "0"})
    route(fake, provider, [limited, limited, VENDORS[provider][2]("recovered")])
    assert await chat_completion(MESSAGES, provider=provider, api_base=fake.url, max_retries=2) == "recovered"
    assert len(fake.requests) == 3


@pytest.mark.parametrize("provider", list(VENDORS))
async def test_persistent_rate_limit_ends_in_a_typed_error(fake, provider):
    route(fake, provider, Resp(429, {"error": {"message": "slow down", "type": "rate_limit_error"}}, headers={"retry-after": "0"}))
    with pytest.raises(LLMRateLimitError):
        await chat_completion(MESSAGES, provider=provider, api_base=fake.url, max_retries=1)
    assert len(fake.requests) == 2  # first try + one retry, then the typed error


@pytest.mark.parametrize("provider", list(VENDORS))
async def test_vendor_5xx_is_retried_and_surfaces_as_provider_error(fake, provider):
    route(fake, provider, Resp(503, {"error": {"message": "overloaded", "type": "overloaded_error"}}))
    with pytest.raises(LLMProviderError):
        await chat_completion(MESSAGES, provider=provider, api_base=fake.url, max_retries=1)
    assert len(fake.requests) == 2


@pytest.mark.parametrize("provider", list(VENDORS))
async def test_a_vendor_that_never_answers_times_out(fake, monkeypatch, provider):
    monkeypatch.setattr(settings, "LLM_TIMEOUT", 0.4)
    route(fake, provider, Resp(200, {}, delay=2.0))
    with pytest.raises(LLMTimeoutError):
        await chat_completion(MESSAGES, provider=provider, api_base=fake.url, max_retries=0)


@pytest.mark.parametrize("provider", list(VENDORS))
async def test_bad_request_is_not_retried_and_is_a_provider_error(fake, provider):
    route(fake, provider, Resp(400, {"error": {"message": "max_tokens too large", "type": "invalid_request_error"}, "type": "error"}))
    with pytest.raises(LLMProviderError) as info:
        await chat_completion(MESSAGES, provider=provider, api_base=fake.url, max_retries=3)
    assert not isinstance(info.value, (LLMAuthenticationError, LLMRateLimitError))
    assert len(fake.requests) == 1


async def test_provider_down_falls_back_to_the_next_vendor():
    with FakeVendor() as both:  # one fake answering both vendors' routes: Anthropic is down, OpenAI works
        both.on("POST", "/v1/messages", Resp(500, {"type": "error", "error": {"type": "api_error", "message": "boom"}}))
        both.on("POST", "/chat/completions", openai_ok("from the fallback"))
        answer = await chat_completion_with_fallback(MESSAGES, ["anthropic", "openai"], max_retries=0, api_base=both.url)
        assert answer == "from the fallback"
        assert [r.path for r in both.requests] == ["/v1/messages", "/chat/completions"]


async def test_every_vendor_down_raises_the_last_typed_error():
    with FakeVendor() as both:
        both.on("POST", "*", Resp(500, {"error": {"message": "down"}}))
        with pytest.raises(LLMProviderError):
            await chat_completion_with_fallback(MESSAGES, ["anthropic", "openai", "mistral"], max_retries=0, api_base=both.url)
        assert len(both.requests) == 3


def sse(events: list[tuple[str, dict]]) -> bytes:
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events).encode()


async def test_openai_streaming_yields_chunks_and_reports_usage(fake):
    chunks = [{"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "gpt-x", "choices": [{"index": 0, "delta": {"role": "assistant", "content": part}, "finish_reason": None}]}
              for part in ("po", "ng")]
    chunks.append({"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "gpt-x", "choices": [], "usage": {"prompt_tokens": 9, "completion_tokens": 2, "total_tokens": 11}})
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    fake.on("POST", "/chat/completions", Resp(200, body.encode(), headers={"Content-Type": "text/event-stream"}))
    usage: dict = {}
    got = [piece async for piece in chat_completion_stream(MESSAGES, provider="openai", api_base=fake.url, usage_sink=usage)]
    assert "".join(got) == "pong"
    assert usage == {"prompt_tokens": 9, "completion_tokens": 2}
    assert fake.requests[0].json()["stream"] is True


async def test_anthropic_streaming_yields_text_deltas(fake):
    events = [
        ("message_start", {"type": "message_start", "message": {"id": "m", "type": "message", "role": "assistant", "model": "c", "content": [], "usage": {"input_tokens": 7, "output_tokens": 1}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "po"}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "ng"}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 2}}),
        ("message_stop", {"type": "message_stop"}),
    ]
    fake.on("POST", "/v1/messages", Resp(200, sse(events), headers={"Content-Type": "text/event-stream"}))
    got = [piece async for piece in chat_completion_stream(MESSAGES, provider="anthropic", api_base=fake.url)]
    assert "".join(got) == "pong"


async def test_stream_started_with_an_auth_error_raises_typed_error(fake):
    fake.on("POST", "/chat/completions", Resp(401, VENDORS["openai"][5]))
    with pytest.raises(LLMAuthenticationError):
        async for _ in chat_completion_stream(MESSAGES, provider="openai", api_base=fake.url):
            pass


async def test_anthropic_tool_call_is_parsed(fake):
    fake.on("POST", "/v1/messages", Resp(200, {
        "id": "m", "type": "message", "role": "assistant", "model": "c", "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": "toolu_1", "name": "get_weather", "input": {"city": "Paris"}}],
        "usage": {"input_tokens": 5, "output_tokens": 4}}))
    tools = [{"type": "function", "function": {"name": "get_weather", "description": "w", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}}}]
    result = await chat_completion_with_usage(MESSAGES, provider="anthropic", api_base=fake.url, tools=tools, max_retries=0)
    assert result["tool_calls"] == [{"id": "toolu_1", "name": "get_weather", "arguments": {"city": "Paris"}}]
    sent = fake.requests[0].json()
    assert sent["tools"][0]["name"] == "get_weather" and "input_schema" in sent["tools"][0]  # translated to Anthropic's own tool schema
