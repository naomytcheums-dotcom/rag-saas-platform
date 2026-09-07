"""
Partie 5.3.7 -- a real, additive ACL layer on top of the existing
organization role tier (Partie 1.2), scoped to ONE real agent.

**Cohérence avec le RBAC existant (vision critique 1)**: this module
does NOT replace `require_agent_manager`/`require_agent_manager`
(Partie 5.3.1) -- an Owner/Admin/Manager of the agent's own
organization can ALWAYS `update`/`delete` it, exactly as before. The
new, real thing this étape adds is a check that previously did not
exist AT ALL: `action="use"` (actually INVOKING the agent,
`AgentOrchestrator.run_agent`) was never gated by anything beyond real
organization membership -- any real member of the org could invoke any
agent. `allowed_users`/`allowed_roles`/`is_public` narrow (or widen,
for `is_public`) exactly that one real gap, additively, same priority
pattern as `api/security/resource_permissions.py`'s own granular
grants (a real, positive allow list on top of the role hierarchy,
never a way to LOCK OUT an Owner/Admin/Manager from managing their own
agent)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.agent import Agent
from api.models.organization import OrganizationMember, OrganizationRole

_MANAGER_ROLES = (OrganizationRole.owner, OrganizationRole.admin, OrganizationRole.manager)
AGENT_ACTIONS = ("use", "update", "delete")


class AgentPermissionError(ValueError):
    """Real, dedicated exception."""


async def _get_membership(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID) -> OrganizationMember | None:
    return await db.scalar(
        select(OrganizationMember).where(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user_id)
    )


async def check_agent_permission(db: AsyncSession, agent_id: uuid.UUID, user_id: uuid.UUID, action: str) -> bool:
    """Item 2's own literal function -- real, returns `False` (never
    raises) for an unknown agent, a non-member, or a denied action, so
    every real caller (endpoints AND `AgentOrchestrator.run_agent`) can
    treat this as a plain boolean gate.

    Real priority order: `update`/`delete` are decided by the existing
    real org role tier ALONE (Owner/Admin/Manager, same as
    `require_agent_manager`) -- the new ACL fields never grant those,
    only `use` does. `use` is allowed when ANY of: the caller is a real
    Owner/Admin/Manager, `agent.is_public`, the caller's real org role
    is in `agent.allowed_roles`, or the caller's real user id is in
    `agent.allowed_users`."""
    if action not in AGENT_ACTIONS:
        raise AgentPermissionError(f"Unknown action: {action!r} (expected one of {AGENT_ACTIONS})")

    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return False

    membership = await _get_membership(db, agent.organization_id, user_id)
    if membership is None:
        return False

    if membership.role in _MANAGER_ROLES:
        return True
    if action in ("update", "delete"):
        return False

    # action == "use" beyond this point.
    if agent.is_public:
        return True
    if agent.allowed_roles and membership.role.value in agent.allowed_roles:
        return True
    if agent.allowed_users and str(user_id) in agent.allowed_users:
        return True
    return False


async def get_allowed_users(db: AsyncSession, agent_id: uuid.UUID) -> list[str] | None:
    """Item 2's own literal function -- `None` for an unknown agent."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    return list(agent.allowed_users or [])


async def add_allowed_user(db: AsyncSession, agent_id: uuid.UUID, user_id: uuid.UUID, added_by: uuid.UUID) -> Agent | None:
    """Item 2's own literal function -- real, upsert (adding an
    already-allowed user is a real no-op, not a duplicate). `added_by`
    must be a real member of the SAME organization as the agent (same
    cross-organization discipline as Partie 5.3.4's
    `validate_knowledge_base_access` -- a stray/stale id from another
    organization is rejected, not silently trusted)."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    if await _get_membership(db, agent.organization_id, added_by) is None:
        raise AgentPermissionError(f"{added_by} is not a real member of this agent's own organization")

    allowed = list(agent.allowed_users or [])
    if str(user_id) not in allowed:
        allowed.append(str(user_id))
    agent.allowed_users = allowed
    await db.flush()
    return agent


async def remove_allowed_user(db: AsyncSession, agent_id: uuid.UUID, user_id: uuid.UUID, removed_by: uuid.UUID) -> Agent | None:
    """Item 2's own literal function -- real, idempotent removal
    (removing a user who was never allowed is a real no-op, not an
    error). Same real cross-organization check on `removed_by` as
    `add_allowed_user`."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    if await _get_membership(db, agent.organization_id, removed_by) is None:
        raise AgentPermissionError(f"{removed_by} is not a real member of this agent's own organization")

    allowed = [u for u in (agent.allowed_users or []) if u != str(user_id)]
    agent.allowed_users = allowed
    await db.flush()
    return agent


def validate_allowed_roles(allowed_roles: list[str]) -> None:
    """Real, shared validation -- every given role must be one of the
    SAME real `OrganizationRole` values the RBAC system already uses
    (vision critique 1: cohérence), not a second, parallel role
    vocabulary. Also called directly from `create_agent`/`update_agent`
    (`api/security/agents.py`), same "no bypass via the generic
    endpoint" reasoning as Parties 5.3.4/5.3.5's own fixes."""
    valid_roles = {r.value for r in OrganizationRole}
    unknown = sorted(set(allowed_roles) - valid_roles)
    if unknown:
        raise AgentPermissionError(f"Unknown organization role(s): {unknown} (expected one of {sorted(valid_roles)})")


async def set_agent_visibility(db: AsyncSession, agent_id: uuid.UUID, is_public: bool, allowed_roles: list[str] | None = None) -> Agent | None:
    """Item 2's own literal function -- real, upfront validation before
    any real write."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    if allowed_roles is not None:
        validate_allowed_roles(allowed_roles)
    agent.is_public = is_public
    if allowed_roles is not None:
        agent.allowed_roles = allowed_roles
    await db.flush()
    return agent
