"""
Etape 1.2.7 -- RBAC (Casbin). Integration tests against the REAL Postgres
database in DATABASE_URL, not the fast SQLite suite -- same reasoning as
tests/test_postgres_integration.py's own module docstring: this exercises
the real `casbin_rule` table (migration 0016) and the real
casbin_async_sqlalchemy_adapter, which SQLite compatibility can't stand
in for (the adapter is Postgres-async-specific).

Calls api/security/rbac.py's init_rbac() DIRECTLY rather than going
through the app/HTTP layer -- api/main.py's lifespan (where init_rbac()
runs in production) never actually fires under this test suite's
ASGITransport-based client fixtures (confirmed empirically; see
rbac.py's own module docstring), so an HTTP-level test here would prove
nothing. Enforcer construction is independent of FastAPI request
handling, so testing it directly is the honest way to verify it for
real, not a workaround.

Uses its own engine (not api.database's module-level singleton) for the
same reason tests/test_postgres_integration.py's pg_engine fixture does:
asyncpg connections are bound to the event loop they were opened on, and
pytest-asyncio gives each test its own loop.
"""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from api.config import settings
from api.security.rbac import ROLE_HIERARCHY, RESOURCE_POLICIES, TIER_POLICIES, init_rbac


@pytest.fixture(scope="module")
async def rbac_engine():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"DATABASE_URL is not reachable -- skipping RBAC integration tests ({exc})")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def enforcer(rbac_engine):
    return await init_rbac(bind_engine=rbac_engine)


async def test_init_rbac_seeds_every_default_policy_exactly_once(enforcer):
    """Validation criterion: default policies load at startup. Exact
    count, not just "some policies exist" -- catches a seed silently
    getting duplicated or dropped."""
    assert len(enforcer.get_policy()) == len(TIER_POLICIES) + len(RESOURCE_POLICIES)
    assert len(enforcer.get_grouping_policy()) == len(ROLE_HIERARCHY)


async def test_init_rbac_is_idempotent_across_restarts(rbac_engine):
    """A real app restart calls init_rbac() again against the same,
    already-seeded table -- must not duplicate rows."""
    first = await init_rbac(bind_engine=rbac_engine)
    second = await init_rbac(bind_engine=rbac_engine)
    assert len(first.get_policy()) == len(second.get_policy())
    assert len(first.get_grouping_policy()) == len(second.get_grouping_policy())


# --------------------------------------- role x resource x action matrix

@pytest.mark.parametrize(
    "role,resource,action,expected",
    [
        # viewer: read-only, exactly matching Etape 1.2.5/1.2.6's tested
        # behavior (viewer can read workspaces, cannot create/update/delete)
        ("viewer", "workspaces", "read", True),
        ("viewer", "workspaces", "create", False),
        ("viewer", "organization", "read", True),
        ("viewer", "organization", "update", False),
        ("viewer", "documents", "read", True),
        ("viewer", "documents", "create", False),
        ("viewer", "conversations", "read", True),
        # member: read + own-resource write, matching Etape 1.2.5's
        # tested behavior (cannot manage members or workspaces)
        ("member", "workspaces", "read", True),
        ("member", "workspaces", "create", False),
        ("member", "documents", "create", True),
        ("member", "documents", "update_own", True),
        ("member", "documents", "delete_own", True),
        ("member", "conversations", "create", True),
        ("member", "members", "read", False),
        # manager: invite + workspace CRUD, NOT role-update/remove --
        # matching Etape 1.2.4's tested behavior exactly
        ("manager", "workspaces", "create", True),
        ("manager", "workspaces", "update", True),
        ("manager", "workspaces", "delete", True),
        ("manager", "members", "read", True),
        ("manager", "members", "create", True),
        ("manager", "members", "update", False),
        ("manager", "members", "delete", False),
        ("manager", "organization", "update", False),
        # admin: full member management, NOT organization delete --
        # matching Etape 1.2.3's tested behavior exactly
        ("admin", "members", "update", True),
        ("admin", "members", "delete", True),
        ("admin", "organization", "update", False),
        ("admin", "organization", "delete", False),
        # owner: everything, including organization update/delete --
        # matching Etape 1.2.2's tested behavior exactly
        ("owner", "organization", "update", True),
        ("owner", "organization", "delete", True),
        ("owner", "members", "delete", True),
        ("owner", "workspaces", "create", True),
        ("owner", "workspaces", "read", True),
    ],
)
async def test_role_resource_action_matrix(enforcer, role, resource, action, expected):
    org_id = "matrix-test-org"
    assert enforcer.enforce(role, org_id, resource, action) is expected


# ------------------------------------------------------- role inheritance

@pytest.mark.parametrize(
    "higher_role,inherited_tier",
    [
        ("admin", "manager"),   # 1 hop:  admin -> manager
        ("owner", "admin"),     # 1 hop:  owner -> admin
        ("owner", "manager"),   # 2 hops: owner -> admin -> manager
    ],
)
async def test_role_inherits_every_lower_tiers_org_tier_grant(enforcer, higher_role, inherited_tier):
    """Explicit validation criterion: role inheritance (admin inherits
    manager, etc.) -- walks the FULL chain, not just one hop (owner's
    org_tier=manager grant only exists via 2 hops: owner->admin->manager).
    org_tier policies only exist at manager/admin/owner (see
    TIER_POLICIES in api/security/rbac.py -- member/viewer have no
    org_tier grant of their own for anything to inherit)."""
    assert enforcer.enforce(higher_role, "inherit-test-org", "org_tier", inherited_tier) is True


async def test_a_role_does_not_inherit_a_higher_roles_grants(enforcer):
    """The inheritance chain only flows downward (owner sees everything
    manager can do), never upward (manager must NOT see what only owner
    can do) -- the exact asymmetry require_org_manager/admin/owner
    already enforce today."""
    assert enforcer.enforce("manager", "inherit-test-org", "org_tier", "admin") is False
    assert enforcer.enforce("manager", "inherit-test-org", "org_tier", "owner") is False
    assert enforcer.enforce("member", "inherit-test-org", "org_tier", "manager") is False
    assert enforcer.enforce("viewer", "inherit-test-org", "workspaces", "create") is False


# --------------------------------------------------- domain (org) isolation

async def test_the_same_user_can_hold_different_roles_in_different_organizations(enforcer):
    """
    THE reason this uses Casbin's domain-aware RBAC instead of the
    spec's literal flat model (`g, user, role`, no domain): a flat model
    stores one role per user, globally -- it cannot represent "Dana is
    Manager in org A but only Member in org B" at all, which is exactly
    how OrganizationMember.role has worked since Etape 1.2.2 (role is
    scoped to a (user, organization) pair). This test proves the domain
    model actually carries that distinction end-to-end against the real
    table, not just in principle -- api/security/rbac.py's
    require_permission() resolves org_id and role per-request the same
    way (via require_org_member -> get_user_org_role), so this is what
    it would see for a real such user.

    Adds temporary per-user grouping policies to prove it, then removes
    them in a finally block -- this runs against the shared real dev
    Postgres, not a disposable per-test database (same convention
    tests/test_postgres_integration.py's own module docstring documents).
    """
    org_a, org_b = "dana-test-org-a", "dana-test-org-b"
    try:
        await enforcer.add_grouping_policy("dana", "manager", org_a)
        await enforcer.add_grouping_policy("dana", "member", org_b)

        assert enforcer.enforce("dana", org_a, "workspaces", "create") is True   # Manager in org A
        assert enforcer.enforce("dana", org_b, "workspaces", "create") is False  # only Member in org B
        assert enforcer.enforce("dana", org_b, "workspaces", "read") is True     # Member can still read
        assert enforcer.enforce("dana", "some-third-org-dana-never-joined", "workspaces", "read") is False
    finally:
        await enforcer.remove_grouping_policy("dana", "manager", org_a)
        await enforcer.remove_grouping_policy("dana", "member", org_b)
