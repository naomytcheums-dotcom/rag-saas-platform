import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services import agent_long_term_memory as ltm


@pytest.mark.asyncio
async def test_extract_stores_facts(monkeypatch):
    db = AsyncMock()
    client = MagicMock()
    client.complete = AsyncMock(return_value='{"preferred_language": "French", "company_name": "Acme"}')

    stored_calls = []

    async def fake_set(db_, agent_id, key, value, *, user_id=None, expires_at=None):
        stored_calls.append((key, value))
        return MagicMock()

    monkeypatch.setattr(ltm, "set_long_term_memory", fake_set)

    out = await ltm.extract_and_store_long_term_memory(
        db, uuid.uuid4(), user_id=uuid.uuid4(),
        user_message="Je parle français", assistant_message="Noté.",
        llm_client=client,
    )
    assert out == {"preferred_language": "French", "company_name": "Acme"}
    assert ("preferred_language", "French") in stored_calls


@pytest.mark.asyncio
async def test_extract_malformed_json_returns_empty():
    db = AsyncMock()
    client = MagicMock()
    client.complete = AsyncMock(return_value="not json at all")
    out = await ltm.extract_and_store_long_term_memory(
        db, uuid.uuid4(), user_id=None,
        user_message="hi", assistant_message="hello",
        llm_client=client,
    )
    assert out == {}


@pytest.mark.asyncio
async def test_extract_llm_failure_returns_empty():
    db = AsyncMock()
    client = MagicMock()
    client.complete = AsyncMock(side_effect=RuntimeError("boom"))
    out = await ltm.extract_and_store_long_term_memory(
        db, uuid.uuid4(), user_id=None,
        user_message="hi", assistant_message="hello",
        llm_client=client,
    )
    assert out == {}


@pytest.mark.asyncio
async def test_extract_empty_messages_returns_empty():
    out = await ltm.extract_and_store_long_term_memory(
        AsyncMock(), uuid.uuid4(), user_id=None,
        user_message="", assistant_message="",
    )
    assert out == {}
