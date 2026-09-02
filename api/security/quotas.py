"""
Partie 1.3.6 -- per-organization resource limits
(api/models/organization_quota.py). Ten dimensions are named in this
step's spec; only THREE map to a real, countable table today: users
(`organization_members`), workspaces (`workspaces`), teams (`teams`).
The other seven -- documents, storage, requests per day/month, API
calls, agents, KB size -- have no corresponding table or endpoint yet
(documents/KB: Partie 2, agents: Partie 5, requests/api_calls: Partie 9's
public API, none built). `check_quota` returns `True` (not enforced) and
`get_quota_usage` reports `None` (not measured, not "0 used") for those
seven -- stored as configuration only, ready the moment the resource
they gate actually exists, rather than silently pretending to enforce a
limit nothing produces usage against.

For the three real dimensions, usage is a LIVE COUNT against the real
table, never a separately maintained counter -- see
api/models/organization_quota.py's own docstring for why (a live count
can't drift from reality the way an increment/decrement pair can).
There is consequently no `organization_usage_counters` table and
`increment_usage` is a documented no-op for these three: the "increment"
already happened, it's the INSERT into organization_members/workspaces/teams
itself.

**Known, accepted race**: check-then-insert (check_quota, then the
caller's own INSERT) is not wrapped in one atomic operation here -- two
requests racing to add the LAST available slot could both pass the
check and both succeed, one over the limit by one. This mirrors every
other check-then-act authorization pattern in this codebase (permission
checks are not serialized against concurrent writes either) and is the
standard, accepted tradeoff for a SOFT usage limit (not a hard
financial/security invariant like a unique email) -- closing it
completely would need a `SELECT ... FOR UPDATE` or a DB-level
constraint per dimension, not attempted here.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.organization import OrganizationMember
from api.models.organization_quota import OrganizationQuota
from api.models.team import Team
from api.models.workspace import Workspace

# resource_type -> (limit column name, live-count query builder). Only
# the three resources with a real table to count get an entry here --
# see this module's own docstring for the other seven.
_LIVE_COUNTERS = {
    "users": ("max_users", lambda organization_id: select(func.count()).select_from(OrganizationMember).where(OrganizationMember.organization_id == organization_id)),
    "workspaces": ("max_workspaces", lambda organization_id: select(func.count()).select_from(Workspace).where(Workspace.organization_id == organization_id)),
    "teams": ("max_teams", lambda organization_id: select(func.count()).select_from(Team).where(Team.organization_id == organization_id)),
}

# The remaining seven dimensions this step's spec names -- stored on
# OrganizationQuota, configurable, but not yet backed by any real table
# or endpoint to measure usage against.
_NOT_YET_TRACKED = (
    "documents", "storage_mb", "requests_per_month", "requests_per_day", "api_calls", "agents", "kb_size_mb",
)

ALL_RESOURCE_TYPES = tuple(_LIVE_COUNTERS) + _NOT_YET_TRACKED


def default_quota_kwargs() -> dict[str, int]:
    """The ten QUOTA_DEFAULT_* settings, keyed to OrganizationQuota's
    own column names -- used both when seeding a new organization's
    quota row and, indirectly, as the shape PATCH validates partial
    updates against."""
    return {
        "max_users": settings.QUOTA_DEFAULT_MAX_USERS,
        "max_workspaces": settings.QUOTA_DEFAULT_MAX_WORKSPACES,
        "max_teams": settings.QUOTA_DEFAULT_MAX_TEAMS,
        "max_documents": settings.QUOTA_DEFAULT_MAX_DOCUMENTS,
        "max_storage_mb": settings.QUOTA_DEFAULT_MAX_STORAGE_MB,
        "max_requests_per_month": settings.QUOTA_DEFAULT_MAX_REQUESTS_PER_MONTH,
        "max_requests_per_day": settings.QUOTA_DEFAULT_MAX_REQUESTS_PER_DAY,
        "max_api_calls": settings.QUOTA_DEFAULT_MAX_API_CALLS,
        "max_agents": settings.QUOTA_DEFAULT_MAX_AGENTS,
        "max_kb_size_mb": settings.QUOTA_DEFAULT_MAX_KB_SIZE_MB,
    }


async def create_default_quota(db: AsyncSession, *, organization_id: uuid.UUID) -> OrganizationQuota:
    """Called once, at organization creation
    (api/security/organizations.py's create_organization_with_owner) --
    does NOT commit, same convention as that function, so it's part of
    the SAME transaction as the organization and its founding Owner
    membership."""
    quota = OrganizationQuota(organization_id=organization_id, **default_quota_kwargs())
    db.add(quota)
    await db.flush()
    return quota


async def get_quota_limits(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, int]:
    """Item 3's literal function -- the configured ceiling for each of
    the ten dimensions, regardless of whether usage against it is
    trackable yet."""
    quota = await db.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == organization_id))
    if quota is None:
        # Every organization gets one at creation (create_default_quota)
        # -- reaching this means an org predates this step, or its quota
        # row was deleted out of band. Fail toward the configured
        # defaults rather than raising, so a pre-existing org isn't
        # suddenly unable to add a single member because of a step
        # added after it already existed.
        return default_quota_kwargs()
    return {name: getattr(quota, name) for name in default_quota_kwargs()}


async def get_quota_usage(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, int | None]:
    """Item 3's literal function -- current usage per dimension. `None`
    for the seven dimensions with no real table to count yet (NOT `0`:
    zero would claim "nothing used," which is a different, false
    statement from "not measured")."""
    usage: dict[str, int | None] = {resource_type: None for resource_type in _NOT_YET_TRACKED}
    for resource_type, (_limit_column, query_builder) in _LIVE_COUNTERS.items():
        usage[resource_type] = await db.scalar(query_builder(organization_id))
    return usage


async def check_quota(db: AsyncSession, organization_id: uuid.UUID, resource_type: str, delta: int = 1) -> bool:
    """
    Item 3's literal function. `True` (not blocked) for any of the seven
    not-yet-tracked dimensions -- see this module's top docstring for
    why that's the honest answer, not a bug: there is nothing to measure
    usage against yet, so nothing can be "over" a limit that has no
    corresponding activity.
    """
    if resource_type not in _LIVE_COUNTERS:
        return True

    limit_column, query_builder = _LIVE_COUNTERS[resource_type]
    limits = await get_quota_limits(db, organization_id)
    current_usage = await db.scalar(query_builder(organization_id))
    return (current_usage + delta) <= limits[limit_column]


async def increment_usage(organization_id: uuid.UUID, resource_type: str, delta: int = 1) -> None:
    """
    Item 3's literal function. A genuine no-op for all ten dimensions
    today -- see this module's top docstring: the three live-counted
    ones need no separate increment (the INSERT that creates the row IS
    the increment, already reflected the next time usage is counted);
    the other seven have no counter storage to increment into at all
    yet (no request-metering infrastructure exists -- Partie 9 isn't
    built). Kept as a real, callable function -- not deleted -- so the
    four functions this step asks for exist with a stable signature;
    wiring an actual counter table behind this for requests_per_day/
    _per_month/api_calls is real, well-scoped future work once
    something exists that would ever call it.
    """
    return None


def _quota_exceeded_error(resource_type: str, limit: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=f"Organization quota exceeded for '{resource_type}' (limit: {limit}). Contact your organization owner to raise it.",
    )


async def require_quota_available(db: AsyncSession, organization_id: uuid.UUID, resource_type: str, delta: int = 1) -> None:
    """Raises if check_quota would return False -- the wrapper actual
    endpoints call, mirroring this codebase's established
    check_x()/require_x() split (e.g. check_user_in_team vs
    require_team_member). 402 Payment Required, not 403/429: this is
    neither a permissions failure nor a request-rate throttle, it is
    "your plan's limit for this resource has been reached" -- the HTTP
    status code that already carries that exact meaning by convention."""
    if not await check_quota(db, organization_id, resource_type, delta):
        limits = await get_quota_limits(db, organization_id)
        limit_column, _query_builder = _LIVE_COUNTERS[resource_type]
        raise _quota_exceeded_error(resource_type, limits[limit_column])
