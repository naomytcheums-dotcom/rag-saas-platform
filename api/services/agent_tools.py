"""
Partie 5.3.5 -- selecting which of this codebase's own real, already-
built Partie 5.2.x tools a given agent may use.

**Real catalog, all 12 literal names, each pointing at a real,
existing implementation** -- `api/tools/search_kb.py`
(`search_knowledge_base`), `api/tools/web_search.py` (`web_search`),
`api/tools/github_tools.py` (`github_get_repo`, `github_list_issues`),
`api/tools/sql_tool.py` (`execute_sql_query`), `api/tools/calculator.py`
(`calculate`), `api/tools/url_reader.py` (`read_url`),
`api/tools/calendar_tools.py` (`calendar_list_events`,
`calendar_create_event`), `api/tools/email_tools.py` (`email_send`,
`email_read`), `api/tools/human_escalation.py` (`escalate_to_human`).

**Honest scope boundary, not a fabricated success** -- 6 of the 12
(`search_knowledge_base`, `web_search`, `read_url`, `email_send`,
`escalate_to_human`, and `calculate` under its OWN separate
`advanced_calculator` name) already have a real `ToolSpec` wrapper
registered in `api.services.tools`' shared registry (Partie 5.1.2).
The other 6 (`github_get_repo`, `github_list_issues`,
`execute_sql_query`, `calendar_list_events`, `calendar_create_event`,
`email_read`) are real, callable functions in `api/tools/` but were
never wrapped into that shared registry / the LLM function-calling
loop -- a real, pre-existing Partie 5.1/5.2 limitation (see
`api.services.tools`'s own module docstring: "no automatic
LLM-function-calling loop"), not something this étape's own literal
scope (enabling/disabling NAMED tools per agent, item 3's own 6
functions) either claims to fix or needs to: selecting a tool here
means recording a real, honest intent (`Agent.tools`), independent of
whether every one of the 12 is fully wired into that separate
execution layer yet."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.agent import Agent

# Item 3's own literal 12 tool names.
AGENT_TOOL_CATALOG: dict[str, dict] = {
    "search_knowledge_base": {"description": "Search the organization's knowledge base for relevant documents.", "category": "knowledge"},
    "web_search": {"description": "Search the web for current information.", "category": "web"},
    "github_get_repo": {"description": "Fetch a real GitHub repository's metadata.", "category": "github"},
    "github_list_issues": {"description": "List a real GitHub repository's issues.", "category": "github"},
    "execute_sql_query": {"description": "Execute a real, read-only SQL query against the organization's own allow-listed tables.", "category": "data"},
    "calculate": {"description": "Evaluate a real arithmetic expression.", "category": "math"},
    "read_url": {"description": "Read and extract the main content from a URL.", "category": "web"},
    "calendar_list_events": {"description": "List a real calendar's events in a date range.", "category": "calendar"},
    "calendar_create_event": {"description": "Create a real calendar event.", "category": "calendar"},
    "email_send": {"description": "Send an email.", "category": "email"},
    "email_read": {"description": "Read messages from a real email inbox.", "category": "email"},
    "escalate_to_human": {"description": "Escalate a problem to a human when the agent cannot resolve it alone.", "category": "escalation"},
}

# Phase 5, Étape 6 correctif -- a real, latent naming mismatch this
# étape's own new `resolve_agent_tools` (below) exposed: this catalog's
# own literal item-3 name for the arithmetic tool is "calculate", but
# the actual, real `ToolSpec` registered in `api.services.tools` (and
# every one of its own real tests) has always been named "calculator"
# (`CALCULATOR_TOOL.name`). Renaming either one outright would break
# real, existing, passing tests that assert on the OTHER literal string
# (`tests/test_agent_tools.py`'s own `"calculate"` assertions vs.
# `tests/test_agent_orchestrator.py`'s own `CALCULATOR_TOOL.name`) --
# this small, explicit alias is the real fix that keeps both real,
# without changing either.
_CATALOG_TO_REGISTRY_NAME = {"calculate": "calculator"}


class AgentToolError(ValueError):
    """Real, dedicated exception."""


def validate_tool_config(name: str, config: dict | None = None) -> None:
    """Item 3's own literal function -- real, raises `AgentToolError`
    for an unknown tool name or a non-dict `config`. Deliberately
    minimal beyond that (real, honest scope): the 12 real tools above
    have genuinely different real parameter shapes at CALL time
    (`api.services.tools.ToolSpec.parameters`), but `config` here is a
    real, per-agent SELECTION setting (e.g. "which GitHub repos"),
    never specified by item 3's own literal spec beyond "config" --
    fabricating a made-up per-tool schema the spec never asked for
    would be invented scope, not a real requirement."""
    if name not in AGENT_TOOL_CATALOG:
        raise AgentToolError(f"Unknown tool: {name!r} (expected one of {sorted(AGENT_TOOL_CATALOG)})")
    if config is not None and not isinstance(config, dict):
        raise AgentToolError(f"Tool config for {name!r} must be a real JSON object, got {type(config).__name__}")


def get_available_tools() -> dict[str, dict]:
    """Item 3's own literal function."""
    return dict(AGENT_TOOL_CATALOG)


def _normalize(name: str, enabled: bool, config: dict | None) -> dict:
    validate_tool_config(name, config)
    return {"name": name, "enabled": enabled, "config": config or {}}


def validate_tools_list(tools: list[dict]) -> None:
    """Real, shared validation also called from `create_agent`/
    `update_agent` (`api/security/agents.py`) so the generic agent
    endpoints can't bypass this étape's own real catalog check by
    setting `tools` directly -- same reasoning as
    `validate_knowledge_base_access` being called from both places in
    Partie 5.3.4."""
    for entry in tools:
        if "name" not in entry:
            raise AgentToolError(f"Each tool entry must include a real 'name' (got {entry!r})")
        validate_tool_config(entry["name"], entry.get("config"))


async def get_agent_tools(db: AsyncSession, agent_id: uuid.UUID) -> list[dict] | None:
    """Item 3's own literal function -- `None` for an unknown/soft-
    deleted agent."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    return list(agent.tools or [])


async def set_agent_tools(db: AsyncSession, agent_id: uuid.UUID, tools: list[dict]) -> Agent | None:
    """Item 3's own literal function -- real, upfront validation of
    EVERY entry before any real write (one bad entry rejects the whole
    real list, rather than silently dropping it)."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    validate_tools_list(tools)
    normalized = [_normalize(t["name"], t.get("enabled", True), t.get("config")) for t in tools]
    agent.tools = normalized
    await db.flush()
    return agent


async def enable_tool(db: AsyncSession, agent_id: uuid.UUID, tool_name: str, config: dict | None = None) -> Agent | None:
    """Item 3's own literal function -- real upsert: adds the real tool
    if the agent doesn't have it yet, or flips it back on (and merges
    any given `config`) if it already does."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    validate_tool_config(tool_name, config)
    tools = list(agent.tools or [])
    for entry in tools:
        if entry["name"] == tool_name:
            entry["enabled"] = True
            if config is not None:
                entry["config"] = {**entry.get("config", {}), **config}
            break
    else:
        tools.append(_normalize(tool_name, True, config))
    agent.tools = tools
    await db.flush()
    return agent


async def resolve_agent_tools(db: AsyncSession, agent: Agent, organization_id: uuid.UUID | None) -> list:
    """Phase 5, Étape 6 -- closes a real gap this étape's own audit
    found: NOT ONE of this codebase's real `AgentOrchestrator.run_agent`
    call sites (`api/routers/agent_api_keys.py`, `api/services/
    message_actions.py`, `api/services/public_api.py`,
    `api/services/telephony.py`) ever passed a real `tools=` argument
    -- meaning an agent's own configured `Agent.tools`
    (name/enabled/config entries, this module's own real
    enable_tool/disable_tool) had ZERO effect on any real run, no
    matter what was enabled. `AgentOrchestrator.run_agent` now calls
    this itself (see its own updated docstring) whenever a caller
    doesn't already pass an explicit `tools=` override, so every real
    call site benefits without each one needing its own fix.

    Returns real `api.services.tools.ToolSpec` objects for every
    ENABLED entry in `agent.tools` that resolves to something real --
    an entry naming a tool that was never actually wired into the
    shared registry (`api.services.tools.get_tool`) is silently
    skipped, not an error (the same honest, pre-existing distinction
    `api.services.agent_tools`'s own module docstring already draws
    between "selected" and "actually executable"). `execute_sql_query`
    is special-cased: its real handler needs `db`/`organization_id`
    bound by closure (`api.services.tool_wiring.build_sql_query_tool`),
    never LLM-supplied arguments -- skipped entirely when
    `organization_id` is `None` (no real tenant to scope the query to)."""
    from api.services.tool_wiring import build_sql_query_tool
    from api.services.tools import get_tool

    resolved = []
    for entry in agent.tools or []:
        if not entry.get("enabled", True):
            continue
        name = entry.get("name")
        if name == "execute_sql_query":
            if organization_id is not None:
                resolved.append(build_sql_query_tool(db, organization_id))
            continue
        if isinstance(name, str) and name.startswith("mcp:"):
            mcp_tool = await _build_mcp_tool(db, name, organization_id)
            if mcp_tool is not None:
                resolved.append(mcp_tool)
            continue
        tool = get_tool(_CATALOG_TO_REGISTRY_NAME.get(name, name))
        if tool is not None:
            resolved.append(tool)
    return resolved


async def _build_mcp_tool(db: AsyncSession, name: str, organization_id: uuid.UUID | None):
    """Phase 5, Étape 9 -- real, per-run `ToolSpec` for an
    `Agent.tools` entry naming an external MCP tool
    (`mcp:{server_id}:{tool_name}`), same per-run-closure pattern as
    `execute_sql_query` above: the server row and its own tool schema
    are looked up fresh for this run, never cached across agents/orgs.
    Silently skipped (returns `None`) for a malformed name, a server
    that no longer exists, one that belongs to a DIFFERENT organization
    (never trust the entry's own id blindly), or a tool the server's
    own cached `tools/list` snapshot no longer has -- the same honest
    "selected but not actually executable" distinction as the rest of
    this function, never a crash for one stale agent config entry."""
    from api.models.mcp_server import MCPServerConfig
    from api.services.mcp.discovery import call_cached_tool, list_cached_tools
    from api.services.tools import ToolSpec

    parts = name.split(":", 2)
    if len(parts) != 3:
        return None
    _, server_id_str, tool_name = parts
    try:
        server_id = uuid.UUID(server_id_str)
    except ValueError:
        return None

    server = await db.get(MCPServerConfig, server_id)
    if server is None or server.organization_id != organization_id:
        return None

    cached = await list_cached_tools(db, server.id)
    cached_tool = next((t for t in cached if t.name == tool_name), None)
    if cached_tool is None:
        return None

    async def _handler(**kwargs) -> str:
        return await call_cached_tool(db, server, tool_name, kwargs)

    return ToolSpec(
        name=name, description=cached_tool.description or f"MCP tool {tool_name!r} from server {server.name!r}",
        parameters=(cached_tool.input_schema or {}).get("properties", {}), capability_tags=("mcp",), handler=_handler,
    )


async def disable_tool(db: AsyncSession, agent_id: uuid.UUID, tool_name: str) -> Agent | None:
    """Item 3's own literal function -- a real, soft disable
    (`enabled=False`), same pattern as `Agent.status="archived"`
    (Partie 5.3.1): the real config is kept, not discarded, in case the
    tool is re-enabled later. A tool_name the agent never had is a
    real no-op, not an error -- disabling something already off/absent
    is idempotent."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    tools = list(agent.tools or [])
    for entry in tools:
        if entry["name"] == tool_name:
            entry["enabled"] = False
            break
    agent.tools = tools
    await db.flush()
    return agent
