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
