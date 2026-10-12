"""Ollama's embedding endpoint (through litellm) returns each item as a plain dict, not an object: the shared call site used `item.index` and crashed
with AttributeError. Found by tests/llm_optin/test_local_agents_ollama.py against a real Ollama server."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import litellm
import pytest

from api.services.embedding_providers import _call_litellm_embedding


async def test_dict_shaped_items_are_read_and_put_back_in_input_order(monkeypatch):
    items = [{"object": "embedding", "index": 1, "embedding": [0.2, 0.2]}, {"object": "embedding", "index": 0, "embedding": [0.1, 0.1]}]
    monkeypatch.setattr(litellm, "aembedding", AsyncMock(return_value=SimpleNamespace(data=items)))

    assert await _call_litellm_embedding("ollama/nomic-embed-text", ["a", "b"]) == [[0.1, 0.1], [0.2, 0.2]]


async def test_object_shaped_items_still_work(monkeypatch):
    items = [SimpleNamespace(index=1, embedding=[0.2]), SimpleNamespace(index=0, embedding=[0.1])]
    monkeypatch.setattr(litellm, "aembedding", AsyncMock(return_value=SimpleNamespace(data=items)))

    assert await _call_litellm_embedding("text-embedding-3-small", ["a", "b"]) == [[0.1], [0.2]]
