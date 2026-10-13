"""Specs 4.2.1 OpenAI, 4.2.2 Voyage AI, 4.2.3 Cohere embeddings -- CONTRACT tests against LOCAL FAKE servers (real product code + real LiteLLM HTTP,
fake vendor). Does NOT prove a real account works: see scripts/validate_embeddings_live.py."""

import pytest

from api.config import settings
from api.services.embedding_providers import (
    EmbeddingAuthenticationError,
    EmbeddingProviderError,
    EmbeddingTimeoutError,
    get_cohere_embeddings,
    get_embeddings_with_fallback,
    get_openai_embeddings,
    get_voyage_embeddings,
)
from vendor_fakes import FakeVendor, Resp

TEXTS = ["alpha", "beta", "gamma"]


def vectors(dim=4):
    return [[float(i + j) for j in range(dim)] for i in range(len(TEXTS))]


def openai_style(shuffle=False):
    data = [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vectors())]
    if shuffle:
        data.reverse()  # vendors do not promise the order; the product must sort by index
    return Resp(200, {"object": "list", "model": "m", "data": data, "usage": {"prompt_tokens": 3, "total_tokens": 3}})


def cohere_style():
    return Resp(200, {"id": "c1", "texts": TEXTS, "embeddings": {"float": vectors()}, "meta": {"api_version": {"version": "1"}, "billed_units": {"input_tokens": 3}}, "response_type": "embeddings_floats"})


# name -> (function, settings key, route, ok response factory, auth header check)
VENDORS = {
    "openai": (get_openai_embeddings, "OPENAI_EMBEDDING_API_KEY", "/embeddings", openai_style),
    "voyage": (get_voyage_embeddings, "VOYAGE_API_KEY", "/embeddings", openai_style),
    "cohere": (get_cohere_embeddings, "COHERE_API_KEY", "/", cohere_style),
}


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_EMBEDDING_API_KEY", "contract-key-openai")
    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "contract-key-voyage")
    monkeypatch.setattr(settings, "COHERE_API_KEY", "contract-key-cohere")


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    import asyncio

    async def instant(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", instant)


@pytest.fixture
def fake():
    with FakeVendor() as f:
        yield f


@pytest.mark.parametrize("name", list(VENDORS))
async def test_request_shape_and_parsed_vectors(fake, name):
    function, _key, path, ok = VENDORS[name]
    fake.on("POST", path, ok())
    result = await function(TEXTS, api_base=fake.url)
    assert result == vectors()
    (request,) = fake.requests
    assert request.headers["authorization"] == f"Bearer contract-key-{name}"
    body = request.json()
    if name == "cohere":
        assert body["texts"] == TEXTS and body["input_type"] == settings.COHERE_EMBEDDING_INPUT_TYPE
        assert body["model"] == settings.COHERE_EMBEDDING_MODEL
        assert body["embedding_types"] == ["float"]  # required by Cohere's /v2/embed
    else:
        assert body["input"] == TEXTS
        assert body["model"] == (settings.OPENAI_EMBEDDING_MODEL if name == "openai" else settings.VOYAGE_EMBEDDING_MODEL).removeprefix("voyage/")


async def test_cohere_input_type_is_forwarded(fake):
    fake.on("POST", "/", cohere_style())
    await get_cohere_embeddings(TEXTS, input_type="search_query", api_base=fake.url)
    assert fake.requests[0].json()["input_type"] == "search_query"


@pytest.mark.parametrize("name", ["openai", "voyage"])
async def test_vectors_are_returned_in_input_order_even_if_the_vendor_shuffles(fake, name):
    function, _key, path, _ok = VENDORS[name]
    fake.on("POST", path, openai_style(shuffle=True))
    assert await function(TEXTS, api_base=fake.url) == vectors()


@pytest.mark.parametrize("name", list(VENDORS))
async def test_authentication_error_is_typed_and_not_retried(fake, name):
    function, _key, path, _ok = VENDORS[name]
    fake.on("POST", path, Resp(401, {"error": {"message": "Incorrect API key provided", "type": "invalid_request_error", "code": "invalid_api_key"}, "message": "invalid api key"}))
    with pytest.raises(EmbeddingAuthenticationError):
        await function(TEXTS, api_base=fake.url)
    assert len(fake.requests) == 1


@pytest.mark.parametrize("name", list(VENDORS))
async def test_a_bad_request_is_not_retried(fake, name):
    function, _key, path, _ok = VENDORS[name]
    fake.on("POST", path, Resp(400, {"error": {"message": "input too long", "type": "invalid_request_error"}, "message": "input too long"}))
    with pytest.raises(EmbeddingProviderError):
        await function(TEXTS, api_base=fake.url)
    assert len(fake.requests) == 1


@pytest.mark.parametrize("name", list(VENDORS))
async def test_missing_key_fails_before_any_network_call(fake, monkeypatch, name):
    function, key, _path, _ok = VENDORS[name]
    monkeypatch.setattr(settings, key, "")
    with pytest.raises(EmbeddingAuthenticationError):
        await function(TEXTS, api_base=fake.url)
    assert fake.requests == []


@pytest.mark.parametrize("name", list(VENDORS))
async def test_rate_limit_ends_in_a_typed_error(fake, name):
    function, _key, path, _ok = VENDORS[name]
    fake.on("POST", path, Resp(429, {"error": {"message": "Rate limit reached", "type": "rate_limit_error"}, "message": "rate limited"}, headers={"retry-after": "0"}))
    with pytest.raises(EmbeddingProviderError):
        await function(TEXTS, api_base=fake.url)
    # one bounded retry layer per vendor: the OpenAI SDK's own (1 + 2), the product's back-off for Voyage/Cohere -- never SDK x product
    assert len(fake.requests) == (3 if name == "openai" else settings.LLM_MAX_RETRIES + 1)


@pytest.mark.parametrize("name", list(VENDORS))
async def test_rate_limit_then_success_recovers(fake, name):
    function, _key, path, ok = VENDORS[name]
    fake.on("POST", path, [Resp(429, {"error": {"message": "slow", "type": "rate_limit_error"}}, headers={"retry-after": "0"}), ok()])
    assert await function(TEXTS, api_base=fake.url) == vectors()
    assert len(fake.requests) == 2


@pytest.mark.parametrize("name", list(VENDORS))
async def test_vendor_5xx_ends_in_a_typed_error(fake, name):
    function, _key, path, _ok = VENDORS[name]
    fake.on("POST", path, Resp(500, {"error": {"message": "internal"}, "message": "internal"}))
    with pytest.raises(EmbeddingProviderError):
        await function(TEXTS, api_base=fake.url)


@pytest.mark.parametrize("name", list(VENDORS))
async def test_vendor_that_never_answers_times_out(fake, name):
    function, _key, path, _ok = VENDORS[name]
    fake.on("POST", path, Resp(200, {}, delay=2.5))
    with pytest.raises(EmbeddingTimeoutError):
        await function(TEXTS, api_base=fake.url, timeout=0.4, max_retries=0)


async def test_provider_down_falls_back_to_the_next_provider():
    with FakeVendor() as both:
        calls = {"n": 0}

        def voyage_down(_req):
            calls["n"] += 1
            return Resp(503, {"detail": "unavailable", "message": "unavailable"})

        both.on("POST", "/embeddings", voyage_down)  # Voyage and OpenAI share this path on the fake: the first provider is down
        with pytest.raises(EmbeddingProviderError):
            await get_embeddings_with_fallback(TEXTS, ["voyage", "openai"], api_base=both.url)
        assert calls["n"] >= 2  # both providers were tried before the last error was raised

    with FakeVendor() as split:
        split.on("POST", "/", Resp(500, {"message": "cohere down"}))
        split.on("POST", "/embeddings", openai_style())
        result = await get_embeddings_with_fallback(TEXTS, ["cohere", "openai"], api_base=split.url)
        assert result == vectors()
        assert split.requests[0].path == "/" and split.requests[-1].path == "/embeddings"
