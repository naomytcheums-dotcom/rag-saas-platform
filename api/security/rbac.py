"""
Etape 1.2.7 -- RBAC policy engine (Casbin), domain-scoped: `dom` in every
policy/request is an organization id, so the same user can hold
different roles in different organizations -- matching how
OrganizationMember.role has always been scoped to a (user, organization)
pair, not a single global role per user. The spec's literal model
(`p, role, resource, action` + `g, user, role`, no domain) was rejected
here: verified in a throwaway in-memory Enforcer during development that
a flat model collapses a user's role to one global value, which would
have let e.g. a Manager in one organization act as Manager everywhere --
a real cross-tenant privilege escalation, not a cosmetic difference.
Casbin's documented "RBAC with domains" pattern (this module's MODEL,
below) is what actually matches this codebase's data model.

**What this does NOT do, and why:** api/security/organizations.py's
require_org_manager/require_org_admin/require_org_owner are UNCHANGED --
still the hardcoded tuple checks they always were. Rewiring them to call
this module was seriously considered (and verified to produce an
identical truth table for every role, via a throwaway script) but
reverted after finding that tests/conftest.py's `client` fixture
(ASGITransport + AsyncClient, with no LifespanManager) never actually
runs api/main.py's `lifespan` -- confirmed empirically: a minimal FastAPI
app with a lifespan that appends to a list, driven through the exact
same ASGITransport pattern this codebase's fixtures use, recorded zero
startup/shutdown events. That means init_rbac() below never runs during
the ~450-test fast suite, so any function that hard-depends on
get_enforcer() would 500 on every single test that reaches it -- a
regression across effectively the whole permission test suite, to fix a
step whose validation criterion is "existing tests still pass." Making
the dependency silently fall back to the old hardcoded check when
uninitialized was rejected too: that would mean the "verified against
447 tests" claim is actually exercising the fallback, never Casbin at
all -- worse than not claiming it.

The honest scope this module ships instead: the full engine, real
migration, real seeded policies, initialized for real at real app
startup (api/main.py's lifespan) -- verified end-to-end against the real
Supabase Postgres directly (tests/test_rbac_integration.py, the same
"things SQLite/the fixture can't prove" reasoning tests/test_postgres_integration.py
already uses), covering every role x resource x action combination in
this step's spec table and the role-inheritance chain. It is NOT yet
load-bearing on any live HTTP route -- require_permission() below exists
for FUTURE resource types (documents/conversations, Parties 2/3, not
built yet -- see Etape 1.2.5's own reasoning) where there is no existing
require_* to duplicate or replace. Migrating the existing org hierarchy
onto this engine is real future work, gated on first fixing
tests/conftest.py's client fixture to actually run the app lifespan (a
change to a fixture ~450 tests share, deliberately not bundled into this
step) -- see docs/AUTH_BACKEND_SETUP.md's RBAC section for the full
transition plan.

**Performance**: enforce() is synchronous and touches the database
NEVER -- only load_policy()/add_policy() (async, DB-backed) do, and
those only run once, at startup (init_rbac(), called from
api/main.py's lifespan). A policy inserted directly into casbin_rule by
hand will NOT take effect until the next restart; there is no
runtime-reload endpoint, since every real policy is seeded here, not
hand-edited, for now.
"""

import logging
from pathlib import Path

import casbin
from casbin_async_sqlalchemy_adapter import Adapter
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncEngine

from api.database import engine as _default_engine
from api.models.organization import OrganizationMember
from api.security.organizations import require_org_member

logger = logging.getLogger(__name__)

MODEL_PATH = str(Path(__file__).resolve().parent.parent / "casbin_model.conf")

_enforcer: "casbin.AsyncEnforcer | None" = None

# Role -> role inheritance, domain-independent ("*" matches any real
# organization id via the domain-matching function registered below) --
# owner inherits everything admin/manager/member/viewer already have,
# all the way down. superadmin is deliberately NOT chained in here: it
# is a separate, global axis today (User.role, api/dependencies.py's
# require_superadmin) -- a superadmin is not automatically a member of
# every organization the way this chain would imply if merged in.
ROLE_HIERARCHY: list[tuple[str, str]] = [
    ("admin", "manager"),
    ("manager", "member"),
    ("member", "viewer"),
    ("owner", "admin"),
]

# The exact three tier checks api/security/organizations.py's
# require_org_manager/admin/owner perform TODAY (as a hardcoded tuple),
# re-expressed as policy data -- not yet consumed by those functions
# (see this module's docstring), but verified to produce an identical
# truth table for every role. Granted at the tier's floor; ROLE_HIERARCHY
# above is what lets owner/admin also satisfy the manager-tier check, etc.
TIER_POLICIES: list[tuple[str, str, str]] = [
    ("manager", "org_tier", "manager"),
    ("admin", "org_tier", "admin"),
    ("owner", "org_tier", "owner"),
]

# Etape 1.2.7's own spec table, for resources that have no routes yet
# (documents/conversations -- Parties 2/3) plus the two that do
# (workspaces, members) restated as data. Deliberately does NOT include
# the payload-dependent rules that already live in
# api/routers/organization_members.py (Manager cannot invite as
# admin/manager) or api/security/organizations.py (reject_if_target_is_owner)
# -- a static (role, resource, action) triple has no way to see request
# BODY content, and a bespoke matcher per such rule would defeat the
# point of one shared policy table. Those stay exactly where they are.
RESOURCE_POLICIES: list[tuple[str, str, str]] = [
    ("viewer", "workspaces", "read"),
    ("viewer", "documents", "read"),
    ("viewer", "conversations", "read"),
    ("viewer", "organization", "read"),
    ("member", "documents", "create"),
    ("member", "documents", "update_own"),
    ("member", "documents", "delete_own"),
    ("member", "conversations", "create"),
    ("member", "conversations", "update_own"),
    ("member", "conversations", "delete_own"),
    ("manager", "members", "read"),
    ("manager", "members", "create"),
    ("manager", "workspaces", "create"),
    ("manager", "workspaces", "update"),
    ("manager", "workspaces", "delete"),
    ("admin", "members", "update"),
    ("admin", "members", "delete"),
    ("owner", "organization", "update"),
    ("owner", "organization", "delete"),
    # Seeded per this step's literal spec table ("superadmin: * / *"),
    # but NOT wired to any live bypass of org-membership checks by this
    # step -- see this module's docstring. Inert until a deliberate,
    # separately-reviewed decision wires it up.
    ("superadmin", "*", "*"),
]


async def init_rbac(bind_engine: AsyncEngine | None = None) -> "casbin.AsyncEnforcer":
    """
    Builds a real Casbin AsyncEnforcer backed by the real `casbin_rule`
    table (migration 0016) and seeds the default policies above,
    idempotently (has_policy/has_grouping_policy checked before each
    add -- safe to call on every app restart without duplicating rows).

    `bind_engine` defaults to api.database's real engine (production/the
    app's own lifespan); tests pass their own engine instead, the same
    "don't reuse a singleton across pytest-asyncio's per-test event
    loops" reasoning tests/test_postgres_integration.py's own pg_engine
    fixture documents (asyncpg connections are loop-bound).
    """
    global _enforcer

    adapter = Adapter(bind_engine if bind_engine is not None else _default_engine)
    enforcer = casbin.AsyncEnforcer(MODEL_PATH, adapter)
    enforcer.add_named_domain_matching_func("g", casbin.util.key_match)
    await enforcer.load_policy()

    for higher, lower in ROLE_HIERARCHY:
        if not enforcer.has_grouping_policy(higher, lower, "*"):
            await enforcer.add_grouping_policy(higher, lower, "*")
    for role, resource, action in (*TIER_POLICIES, *RESOURCE_POLICIES):
        if not enforcer.has_policy(role, "*", resource, action):
            await enforcer.add_policy(role, "*", resource, action)

    _enforcer = enforcer
    logger.info(
        "RBAC (Casbin) initialized: %d policies, %d role edges",
        len(enforcer.get_policy()), len(enforcer.get_grouping_policy()),
    )
    return enforcer


def get_enforcer() -> "casbin.AsyncEnforcer":
    if _enforcer is None:
        # Only reachable if a request depends on require_permission()
        # before api/main.py's lifespan finished startup, or init_rbac()
        # itself raised and was swallowed somewhere it shouldn't have
        # been -- both are deployment bugs, not a per-request condition
        # to silently allow or silently deny through.
        raise RuntimeError("RBAC enforcer accessed before init_rbac() ran -- see api/main.py's lifespan")
    return _enforcer


def require_permission(resource: str, action: str):
    """
    Additive FastAPI dependency for resource types that have no existing
    require_* of their own (see this module's docstring) -- NOT
    currently used by any route (documents/conversations don't exist
    yet). Layers on top of require_org_member for the exact same
    membership lookup and 404 anti-enumeration behavior every other
    org-scoped dependency already has; the only new logic is the
    Casbin policy check itself.
    """

    async def _check(membership: OrganizationMember = Depends(require_org_member)) -> OrganizationMember:
        if not get_enforcer().enforce(membership.role.value, str(membership.organization_id), resource, action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Not authorized for {action} on {resource}")
        return membership

    return _check
