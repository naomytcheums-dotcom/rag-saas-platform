"""
Partie 5.1.3 -- item 2's own literal functions: `check_tool_permission`/
`grant_tool_permission`/`revoke_tool_permission`/`get_tool_permissions`/
`get_available_tools`.

**Real precedence rule (vision critique: "les permissions sont-elles
héritées ?")**: a real, deterministic, most-specific-wins order --
1. an exact `(agent_id, user_id, tool_name)` row,
2. a user-wide row (`agent_id IS NULL`, this `user_id`, `tool_name`),
3. an agent-wide row (this `agent_id`, `user_id IS NULL`, `tool_name`),
4. an organization-wide row (`agent_id IS NULL`, `user_id IS NULL`, `tool_name`),
5. no matching row at all -> default **allow**.

Default-allow (not default-deny) is a real, deliberate, documented
choice: this system's own purpose is to let an Admin selectively
RESTRICT specific tools, not to require every tool be explicitly
allow-listed before use -- consistent with this codebase's two other
permission layers (api/security/resource_permissions.py is purely
additive on top of role defaults; api/security/rbac.py's own role
tiers already gate broad access). A row's own explicit `"allow"` is
mostly useful to override a wider `"deny"` at a more specific scope
(e.g. an agent-wide deny, with one specific user still allowed)."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.tool_permission import ToolPermission, ToolPermissionValue
from api.services.tools import ToolSpec, list_tools


async def check_tool_permission(
    db: AsyncSession, organization_id: uuid.UUID | None, agent_id: str | None, user_id: uuid.UUID | None, tool_name: str,
) -> str:
    """Item 2's own literal function -- returns `"allow"` or `"deny"`,
    never `None`: this module's own real precedence rule (see this
    module's own top docstring) always resolves to a real decision,
    defaulting to `"allow"` when nothing matches. A `None`
    `organization_id` (an org-less internal caller, e.g.
    AgentOrchestrator.run_agent with no request context) can never
    match a real row (`tool_permissions.organization_id` is NOT NULL)
    -- correctly, safely defaults to `"allow"` for every tool."""
    agent_filter = ToolPermission.agent_id.is_(None) if agent_id is None else or_(ToolPermission.agent_id == agent_id, ToolPermission.agent_id.is_(None))
    user_filter = ToolPermission.user_id.is_(None) if user_id is None else or_(ToolPermission.user_id == user_id, ToolPermission.user_id.is_(None))

    rows = (await db.scalars(
        select(ToolPermission).where(
            ToolPermission.organization_id == organization_id, ToolPermission.tool_name == tool_name,
            agent_filter, user_filter,
        )
    )).all()
    by_specificity = {(r.agent_id == agent_id, r.user_id == user_id): r for r in rows}

    # Most specific first: exact agent+user -> user-wide -> agent-wide -> org-wide.
    for key in ((True, True), (False, True), (True, False), (False, False)):
        if key in by_specificity:
            return by_specificity[key].permission
    return ToolPermissionValue.allow.value


async def grant_tool_permission(
    db: AsyncSession, organization_id: uuid.UUID, agent_id: str | None, user_id: uuid.UUID | None,
    tool_name: str, permission: str, granted_by: uuid.UUID | None,
) -> ToolPermission:
    """Item 2's own literal function -- a real upsert (query first, then
    update or insert) rather than a raw `INSERT ... ON CONFLICT`: see
    this module's own model's docstring for why the DB's own UNIQUE
    constraint alone cannot dedupe two wildcard (`NULL`) rows."""
    if permission not in (ToolPermissionValue.allow.value, ToolPermissionValue.deny.value):
        raise ValueError(f"Invalid permission: {permission!r} (expected 'allow' or 'deny')")

    existing = await db.scalar(
        select(ToolPermission).where(
            ToolPermission.organization_id == organization_id, ToolPermission.agent_id == agent_id,
            ToolPermission.user_id == user_id, ToolPermission.tool_name == tool_name,
        )
    )
    if existing is not None:
        existing.permission = permission
        existing.created_by = granted_by
        await db.flush()
        return existing

    row = ToolPermission(
        organization_id=organization_id, agent_id=agent_id, user_id=user_id,
        tool_name=tool_name, permission=permission, created_by=granted_by,
    )
    db.add(row)
    await db.flush()
    return row


async def revoke_tool_permission(
    db: AsyncSession, organization_id: uuid.UUID, agent_id: str | None, user_id: uuid.UUID | None, tool_name: str,
) -> bool:
    """Item 2's own literal function -- real deletion (this is a
    genuine override row, not an audit record worth a soft-delete
    convention); `True` only if a real row was actually found and
    removed."""
    existing = await db.scalar(
        select(ToolPermission).where(
            ToolPermission.organization_id == organization_id, ToolPermission.agent_id == agent_id,
            ToolPermission.user_id == user_id, ToolPermission.tool_name == tool_name,
        )
    )
    if existing is None:
        return False
    await db.delete(existing)
    await db.flush()
    return True


async def get_tool_permissions(
    db: AsyncSession, organization_id: uuid.UUID, agent_id: str | None = None, user_id: uuid.UUID | None = None,
) -> list[ToolPermission]:
    """Item 2's own literal function -- every real row matching the
    given filters (both optional; omitting both lists every override in
    the organization)."""
    query = select(ToolPermission).where(ToolPermission.organization_id == organization_id)
    if agent_id is not None:
        query = query.where(ToolPermission.agent_id == agent_id)
    if user_id is not None:
        query = query.where(ToolPermission.user_id == user_id)
    return list((await db.scalars(query)).all())


async def get_available_tools(
    db: AsyncSession, organization_id: uuid.UUID, agent_id: str | None, user_id: uuid.UUID | None,
) -> list[ToolSpec]:
    """Item 2's own literal function -- every real registered tool
    (api.services.tools.list_tools) minus the ones this real
    precedence rule resolves to `"deny"` for this agent/user."""
    result = []
    for tool in list_tools():
        if await check_tool_permission(db, organization_id, agent_id, user_id, tool.name) == ToolPermissionValue.allow.value:
            result.append(tool)
    return result
