"""Network-free checks for Mem0's explicit local resource cleanup."""

import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from api.services import mem0_service


@pytest.fixture
def memory_cache(monkeypatch):
    cache = {}
    monkeypatch.setattr(mem0_service, "_INSTANCES", cache)
    return cache


def test_close_all_memories_closes_all_local_clients_and_clears_cache(memory_cache):
    vector_client = Mock()
    telemetry_client = Mock()
    memory = SimpleNamespace(
        vector_store=SimpleNamespace(is_local=True, client=vector_client),
        _telemetry_vector_store=SimpleNamespace(is_local=True, client=telemetry_client),
        _entity_store=SimpleNamespace(is_local=True, client=vector_client),
        close=Mock(),
    )
    memory_cache[(uuid.uuid4(), uuid.uuid4())] = memory

    mem0_service.close_all_memories()
    mem0_service.close_all_memories()

    vector_client.close.assert_called_once_with()
    telemetry_client.close.assert_called_once_with()
    memory.close.assert_called_once_with()
    assert memory_cache == {}


def test_close_all_memories_logs_failures_and_continues(memory_cache, caplog):
    failing_client = Mock()
    failing_client.close.side_effect = RuntimeError("private-credential-must-not-be-logged")
    succeeding_client = Mock()
    failing_memory = SimpleNamespace(
        vector_store=SimpleNamespace(is_local=True, client=failing_client),
        _telemetry_vector_store=SimpleNamespace(is_local=True, client=succeeding_client),
        close=Mock(side_effect=OSError("private-host-must-not-be-logged")),
    )
    other_memory = SimpleNamespace(close=Mock())
    memory_cache[(uuid.uuid4(), uuid.uuid4())] = failing_memory
    memory_cache[(uuid.uuid4(), uuid.uuid4())] = other_memory

    with caplog.at_level(logging.WARNING, logger=mem0_service.__name__):
        mem0_service.close_all_memories()

    failing_client.close.assert_called_once_with()
    succeeding_client.close.assert_called_once_with()
    other_memory.close.assert_called_once_with()
    assert memory_cache == {}
    assert "local vector_store client close failed (RuntimeError)" in caplog.text
    assert "memory close failed (OSError)" in caplog.text
    assert "private-credential" not in caplog.text
    assert "private-host" not in caplog.text


def test_close_all_memories_does_not_contact_remote_vector_clients(memory_cache):
    remote_client = Mock()
    memory_cache[(uuid.uuid4(), uuid.uuid4())] = SimpleNamespace(
        vector_store=SimpleNamespace(is_local=False, client=remote_client), close=Mock(),
    )
    mem0_service.close_all_memories()
    remote_client.close.assert_not_called()
    assert memory_cache == {}


async def test_application_lifespan_closes_memories_without_connecting(monkeypatch):
    import api.main as main

    session = AsyncMock()
    session_factory = Mock(return_value=AsyncMock())
    session_factory.return_value.__aenter__.return_value = session
    monkeypatch.setattr(main, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(main, "refresh_jwt_key_cache", AsyncMock())
    monkeypatch.setattr(main, "init_rbac", AsyncMock())
    for name in (
        "install_system_log_handler", "configure_structured_logging", "install_loki_handler",
        "setup_llm_observability", "setup_error_tracking", "setup_tracing",
    ):
        monkeypatch.setattr(main, name, Mock())
    close = Mock()
    monkeypatch.setattr(main, "close_all_memories", close)

    async with main.lifespan(main.app):
        close.assert_not_called()
    close.assert_called_once_with()
