"""Specs 4.1.5, 13.2.7 - the `ollama` and `openai_compatible` providers against a REAL local Ollama server. Opt-in, free, no key:

    RUN_REAL_LLM_TESTS=1 LOCAL_LLM_BASE_URL=http://127.0.0.1:11434 LOCAL_LLM_MODEL=qwen2.5:3b pytest tests/llm_optin/test_local_llm_providers.py -q

Covers a plain answer, streaming (with usage), tool calls, and the failures: unknown model, nothing listening, and a server that dies in the
middle of a streamed answer (a real socket that closes after the first chunk -- Ollama itself is never stopped, it may be shared).
"""

import asyncio
import json
import os

import pytest

from api.config import settings
from api.services.llm_providers import LLMError, chat_completion, chat_completion_stream, chat_completion_with_usage

pytestmark = pytest.mark.skipif(os.environ.get("RUN_REAL_LLM_TESTS") != "1", reason="real-LLM tests are opt-in: set RUN_REAL_LLM_TESTS=1")

BASE_URL = os.environ.get("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("LOCAL_LLM_MODEL", "qwen2.5:3b")
PROVIDERS = ["ollama", "openai_compatible"]
MESSAGES = [{"role": "user", "content": "Reply with the single word: pong"}]


@pytest.fixture(autouse=True)
def local_endpoints(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", BASE_URL)
    monkeypatch.setattr(settings, "OPENAI_COMPATIBLE_BASE_URL", f"{BASE_URL}/v1")
    monkeypatch.setattr(settings, "LLM_TIMEOUT", 600)


def _use(monkeypatch, provider: str, base_url: str) -> None:
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL" if provider == "ollama" else "OPENAI_COMPATIBLE_BASE_URL", base_url if provider == "ollama" else f"{base_url}/v1")


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_a_plain_conversation_gets_an_answer(provider):
    answer = await chat_completion(MESSAGES, provider=provider, model=MODEL, max_tokens=20, max_retries=0)
    assert "pong" in answer.lower()


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_streaming_yields_tokens_and_reports_usage(provider):
    usage: dict = {}
    chunks = [chunk async for chunk in chat_completion_stream(MESSAGES, provider=provider, model=MODEL, usage_sink=usage, max_tokens=20)]
    assert len(chunks) >= 1
    assert "pong" in "".join(chunks).lower()
    assert usage.get("completion_tokens")


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_the_model_can_call_a_tool(provider):
    tools = [{"type": "function", "function": {
        "name": "get_weather", "description": "Current weather of a city",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
    }}]
    messages = [{"role": "user", "content": "What is the weather in Paris right now? Use the tool."}]
    result = await chat_completion_with_usage(messages, provider=provider, model=MODEL, tools=tools, max_tokens=100, max_retries=0)
    assert [call["name"] for call in result["tool_calls"]] == ["get_weather"]
    assert "paris" in str(result["tool_calls"][0]["arguments"]).lower()


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_an_unknown_model_is_a_clean_llm_error(provider):
    with pytest.raises(LLMError):
        await chat_completion(MESSAGES, provider=provider, model="no-such-model:1b", max_tokens=5, max_retries=0)


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_nothing_listening_is_a_clean_llm_error(provider, monkeypatch):
    _use(monkeypatch, provider, "http://127.0.0.1:9")
    with pytest.raises(LLMError):
        await chat_completion(MESSAGES, provider=provider, model=MODEL, max_tokens=5, max_retries=0)


async def _serve_one_chunk_then_die():
    """An OpenAI-style streaming endpoint whose server vanishes after the first chunk (no final chunk, no [DONE], connection reset)."""
    async def handle(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\n\r\n")
        event = "data: " + json.dumps({"id": "x", "object": "chat.completion.chunk", "created": 0, "model": "m", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "po"}}]}) + "\n\n"
        writer.write(f"{len(event.encode()):x}\r\n{event}\r\n".encode())
        await writer.drain()
        await asyncio.sleep(0.5)  # an immediate reset would discard the chunk before the client reads it
        writer.transport.abort()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


async def test_a_server_dying_mid_stream_raises_instead_of_ending_quietly(monkeypatch):
    server, port = await _serve_one_chunk_then_die()
    _use(monkeypatch, "openai_compatible", f"http://127.0.0.1:{port}")
    received: list[str] = []
    try:
        with pytest.raises(LLMError) as caught:
            async for chunk in chat_completion_stream(MESSAGES, provider="openai_compatible", model=MODEL):
                received.append(chunk)
    finally:
        server.close()
    assert received == ["po"]
    assert caught.value is not None
