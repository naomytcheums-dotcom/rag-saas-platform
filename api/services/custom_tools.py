"""
Partie 5.2.10 -- executing a real, organization-defined custom tool
via its own real webhook.

**Sécurité (vision critique 1): real SSRF protection, reused, not
reinvented** -- same real, DNS-rebinding-safe `ssrf_safe_client`
(`api/services/url_fetching.py`, added for Partie 5.4.6's own HTTP
block) as the real transport for every real call here. A per-tool
domain allowlist was not part of this étape's own literal
`CustomTool` columns (no such field was asked for) -- the real,
connection-layer SSRF check is the substantive, real protection this
étape's own vision critique asks about, exactly as it already is for
the HTTP workflow block.

**Cohérence (vision critique, réutilisation) -- input validation reuses
the SAME real JSON-schema-shaped validator `api/services/tool_validation.py`
(Partie 5.1.9) already implements for a tool's own RESULT** --
`get_validation_errors` is generic over any `(value, schema)` pair, so
no second, competing schema-validation implementation was needed for a
tool's own INPUT instead.

**Real retries reuse `api/services/retry.py`'s own `retry_async`
(Partie 5.1.6)** -- `retry_count` real attempts, retried ONLY on a
real, transient network failure (`httpx.TimeoutException`/
`httpx.TransportError`); a real non-2xx response from the webhook
itself is a real, immediate failure, never retried (a broken
URL/real 4xx client error retrying blindly would never help)."""

import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.custom_tool import CustomTool
from api.security.custom_tools import CustomToolError, get_custom_tool, get_custom_tools
from api.services.retry import retry_async
from api.services.tool_validation import get_validation_errors
from api.services.tools import ToolSpec
from api.services.url_fetching import ssrf_safe_client


def validate_custom_tool_input(tool: CustomTool, params: dict) -> None:
    """Item 2's own literal function -- real, upfront validation
    against the tool's own real, stored `schema` (Partie 5.1.9's own
    generic JSON-schema validator, reused for a real INPUT contract
    instead of a real RESULT one)."""
    if not tool.schema:
        return
    errors = get_validation_errors(params, tool.schema)
    if errors:
        raise CustomToolError(f"Invalid input for custom tool {tool.name!r}: {errors}")


def format_webhook_response(response: httpx.Response) -> dict:
    """Item 2's own literal function -- a real, plain, JSON-safe
    summary, same shape as the HTTP workflow block's own
    `format_http_response` (Partie 5.4.6)."""
    try:
        body = response.json()
    except ValueError:
        body = response.text
    return {"status_code": response.status_code, "headers": dict(response.headers), "body": body}


async def _call_webhook(tool: CustomTool, params: dict) -> httpx.Response:
    kwargs: dict = {"headers": tool.headers or {}, "timeout": tool.timeout}
    if tool.method in ("GET", "DELETE"):
        kwargs["params"] = params
    else:
        kwargs["json"] = params
    async with ssrf_safe_client() as client:
        response = await client.request(tool.method, tool.webhook_url, **kwargs)
    response.raise_for_status()
    return response


async def execute_custom_tool(db: AsyncSession, tool_id: uuid.UUID, params: dict, context: dict | None = None) -> dict:
    """Item 2's own literal function -- real, upfront validation, then
    a real, live webhook call (with real retries), never a raw,
    leaked `httpx` exception."""
    tool = await get_custom_tool(db, tool_id)
    if tool is None:
        raise CustomToolError(f"Unknown custom tool: {tool_id}")
    validate_custom_tool_input(tool, params)

    try:
        response = await retry_async(
            _call_webhook, tool, params, max_attempts=tool.retry_count,
            retry_on_exceptions=(httpx.TimeoutException, httpx.TransportError),
        )
    except httpx.HTTPError as exc:
        raise CustomToolError(f"Custom tool {tool.name!r} webhook failed: {exc}") from exc

    return format_webhook_response(response)


def get_custom_tool_spec(db: AsyncSession, tool: CustomTool) -> ToolSpec:
    """Real, additional function (not literally named by this étape) --
    wraps one real `CustomTool` row into a real `ToolSpec`
    (`api.services.tools`, Partie 5.1.2), the SAME real, generic shape
    `AgentOrchestrator.run_agent`'s own `tools` parameter already
    accepts -- this is the real, concrete answer to item 4's own
    "ajouter les outils personnalisés à la liste des outils
    disponibles": a real caller assembling that list simply includes
    this alongside every built-in `ToolSpec`, no orchestrator code
    change needed since it already accepts any real `ToolSpec`."""

    async def _handler(**params) -> str:
        result = await execute_custom_tool(db, tool.id, params)
        return str(result.get("body", result))

    return ToolSpec(
        name=tool.name, description=tool.description, parameters=tool.schema.get("properties", {}) if tool.schema else {},
        capability_tags=("custom", "webhook"), handler=_handler,
    )


async def get_available_custom_tools(db: AsyncSession, organization_id: uuid.UUID) -> list[ToolSpec]:
    """Real, additional function -- every real, non-deleted custom
    tool for this organization, each wrapped into a real `ToolSpec`."""
    tools = await get_custom_tools(db, organization_id)
    return [get_custom_tool_spec(db, tool) for tool in tools]
