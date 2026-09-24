"""
Phase 5, Étape 9 -- this platform's own MCP SERVER role: exposes OUR
tool registry (`api/services/tools.py`) to EXTERNAL MCP clients over a
real, wire-compatible subset of the MCP protocol (`tools/list`-shaped
`GET`, `tools/call`-shaped `POST`, JSON bodies matching
`mcp.types.ListToolsResult`/`CallToolResult`'s own real field names --
verified against the installed `mcp==2.0.0` SDK's own type definitions,
not guessed).

**Real auth reuse, not a new mechanism**: gated by
`require_public_api_scope("mcp:tools")`
(api/security/public_api_auth.py), the exact same org-scoped
`X-API-Key` header, rate-limiting, and quota enforcement every other
`/v1/*` public endpoint already gets -- an external MCP client is,
from this platform's own point of view, just another public API
caller. No parallel auth system built for this one surface.

**Deliberate scope for this étape**: only the static, built-in tool
registry (`list_tools()`/`get_tool()`) is exposed -- NOT this
organization's own custom webhook tools
(`api/models/custom_tool.py`) or per-run tools like `execute_sql_query`
(`api/services/tool_wiring.build_sql_query_tool`, which needs a real
`organization_id`/`db` bound by closure, not appropriate to expose
generically to an arbitrary external MCP client without a much more
careful per-tool allowlist review). Traced, not silently missing --
see ROADMAP.md.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_db
from api.models.organization_api_key import OrganizationAPIKey
from api.security.public_api_auth import require_public_api_scope
from api.services.custom_tools import execute_custom_tool, get_available_custom_tools
from api.services.tool_timeout import ToolTimeoutError, execute_tool_with_timeout
from api.services.tool_validation import get_validation_errors
from api.services.tools import get_tool, list_tools, tool_input_schema
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/mcp/v1", tags=["mcp-server"])


def _tool_to_mcp_shape(tool) -> dict[str, Any]:
    return {"name": tool.name, "description": tool.description, "input_schema": tool_input_schema(tool)}


@router.get("/tools")
async def list_tools_endpoint(
    key: OrganizationAPIKey = Depends(require_public_api_scope("mcp:tools")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Real `tools/list`-shaped response -- `{"tools": [...]}`, matching
    `mcp.types.ListToolsResult`'s own real field name.

    Includes both the static builtin registry AND this organization's
    own custom webhook tools (`api/models/custom_tool.py`)."""
    builtin = [_tool_to_mcp_shape(tool) for tool in list_tools()]
    custom = [
        {"name": spec.name, "description": spec.description, "input_schema": spec.input_schema}
        for spec in await get_available_custom_tools(db, key.organization_id)
    ]
    return {"tools": builtin + custom}


@router.post("/tools/{tool_name}/call")
async def call_tool_endpoint(
    tool_name: str,
    payload: dict[str, Any],
    _key: OrganizationAPIKey = Depends(require_public_api_scope("mcp:tools")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Real `tools/call`-shaped response -- `{"content": [{"type": "text", "text": ...}], "is_error": bool}`,
    matching `mcp.types.CallToolResult`/`TextContent`'s own real field
    names. Validates arguments against the tool's own real JSON-schema
    (same `tool_validation.get_validation_errors` the internal
    function-calling loop already uses, api/services/agent_orchestrator.py)
    before ever invoking the real handler."""
    tool = get_tool(tool_name)
    if tool is None:
        # Try as a custom tool for this organization
        custom_specs = await get_available_custom_tools(db, _key.organization_id)
        matching = next((s for s in custom_specs if s.name == tool_name), None)
        if matching is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown tool: {tool_name!r}")

        arguments = payload.get("arguments", payload) if isinstance(payload, dict) else {}
        errors = get_validation_errors(arguments, matching.input_schema)
        if errors:
            return {"content": [{"type": "text", "text": f"Invalid arguments: {'; '.join(errors)}"}], "is_error": True}

        try:
            result = await execute_custom_tool(db, matching.id, arguments)
        except Exception as exc:
            return {"content": [{"type": "text", "text": f"Tool execution failed: {exc}"}], "is_error": True}

        return {"content": [{"type": "text", "text": str(result)}], "is_error": False}

    arguments = payload.get("arguments", payload) if isinstance(payload, dict) else {}
    errors = get_validation_errors(arguments, tool_input_schema(tool))
    if errors:
        return {"content": [{"type": "text", "text": f"Invalid arguments: {'; '.join(errors)}"}], "is_error": True}

    try:
        result = await execute_tool_with_timeout(tool, arguments)
    except ToolTimeoutError as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "is_error": True}
    except Exception as exc:  # noqa: BLE001 -- a real, external MCP client must get a real error result, never an unhandled 500 leaking internals
        return {"content": [{"type": "text", "text": f"Tool execution failed: {exc}"}], "is_error": True}

    return {"content": [{"type": "text", "text": result}], "is_error": False}
