"""Tests for the 4 IBM Bob 2.0 MCP tools (api/services/mcp/builtin_tools.py).

These are the 4 real tools named in agents.md's own section 3.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.mcp import builtin_tools as bt


def test_list_builtin_tools_returns_the_4_agents_md_tools():
    tools = bt.list_builtin_tools()
    names = {t["name"] for t in tools}
    assert names == {
        "create_rag_agent",
        "get_failure_report",
        "update_retrieval_config",
        "run_eval_benchmark",
    }


def test_get_builtin_tool_returns_none_for_unknown():
    assert bt.get_builtin_tool("nonexistent") is None


def test_get_builtin_tool_returns_spec_for_known():
    spec = bt.get_builtin_tool("create_rag_agent")
    assert spec is not None
    assert "handler" in spec
    assert "input_schema" in spec


@pytest.mark.asyncio
async def test_call_builtin_tool_unknown_name_returns_error():
    db = AsyncMock()
    result = await bt.call_builtin_tool(db, "does_not_exist", {})
    assert result["is_error"] is True
    assert "Unknown builtin tool" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_call_builtin_tool_invalid_uuid_returns_error():
    db = AsyncMock()
    result = await bt.call_builtin_tool(
        db, "create_rag_agent", {"organization_id": "not-a-uuid", "name": "test"}
    )
    assert result["is_error"] is True
    assert "Invalid organization_id" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_create_rag_agent_without_name_returns_error():
    db = AsyncMock()
    org = str(uuid.uuid4())
    result = await bt.call_builtin_tool(db, "create_rag_agent", {"organization_id": org})
    assert result["is_error"] is True
    assert "name is required" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_create_rag_agent_happy_path():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    org = str(uuid.uuid4())
    result = await bt.call_builtin_tool(
        db,
        "create_rag_agent",
        {"organization_id": org, "name": "Support Bot", "retrieval_config": {"top_k": 10}},
    )
    assert result["is_error"] is False
    assert "agent_id" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_update_retrieval_config_empty_config_returns_error():
    db = AsyncMock()
    result = await bt.call_builtin_tool(
        db,
        "update_retrieval_config",
        {
            "organization_id": str(uuid.uuid4()),
            "agent_id": str(uuid.uuid4()),
            "config": {},
        },
    )
    assert result["is_error"] is True
    assert "non-empty object" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_get_failure_report_no_results_returns_empty():
    db = AsyncMock()
    db.scalars = AsyncMock(return_value=MagicMock(all=lambda: []))
    result = await bt.call_builtin_tool(
        db,
        "get_failure_report",
        {
            "organization_id": str(uuid.uuid4()),
            "run_id": str(uuid.uuid4()),
        },
    )
    assert result["is_error"] is False
    assert '"failures": []' in result["content"][0]["text"]
