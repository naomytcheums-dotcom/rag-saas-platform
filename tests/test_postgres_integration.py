"""
Integration tests against the REAL Postgres database in DATABASE_URL (the
Supabase dev instance) -- deliberately separate from tests/test_auth_*.py,
which run against in-memory SQLite for speed. What this file exists to
catch that SQLite cannot: real unique/foreign-key constraint enforcement,
real ON DELETE CASCADE, and the actual Alembic-applied schema.

Builds its OWN engine/session rather than importing api.database's
module-level singleton: asyncpg connections are bound to the event loop
they were opened on, and reusing a singleton across pytest-asyncio's
per-test loops caused exactly that failure mode (connections silently
attached to a dead loop). A fresh engine scoped to this module's own loop
sidesteps it entirely -- the same reason tests/conftest.py's SQLite
fixtures build a fresh engine per test rather than reusing the app's.

Every test creates its own uniquely-emailed user and removes it in a
finally block -- this runs against a shared dev database, not a
disposable per-test one, so cleanup is not optional. Skips the whole
module (not a failure) if DATABASE_URL isn't reachable, so CI/contributors
without a configured Postgres aren't blocked.
"""

import datetime as dt
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.database import get_db
from api.main import app
from api.models.consent_reactivation_token import ConsentReactivationToken
from api.models.lockout_recovery_token import TwoFactorLockoutRecoveryToken
from api.models.oauth import OAuthAccount, OAuthProvider
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.invitation import Invitation
from api.models.custom_domain import CustomDomain
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.ssl_certificate import SSLCertificate
from api.security.secret_encryption import encrypt_secret
from api.models.organization_branding import OrganizationBranding
from api.models.organization_quota import OrganizationQuota
from api.models.organization_settings import OrganizationSettings
from api.models.organization_usage import OrganizationUsage, OrganizationUsageDetail
from api.models.resource_permission import ResourcePermission
from api.models.team import Team, TeamMember, TeamRole
from api.models.workspace import Workspace
from api.models.recovery_code import TwoFactorRecoveryCode
from api.models.restore_token import AccountRestoreToken
from api.models.revoked_token import RevokedAccessToken
from api.models.session import Session as SessionModel
from api.models.token import EmailVerificationToken
from api.models.user import User

# Loop scope is set globally to "session" in pyproject.toml, not pinned
# per-file here -- a per-file "module" scope was closing this file's loop
# before other integration test files ran in the same `pytest` invocation,
# handing them a dead loop (asyncpg connections are loop-bound). See
# pyproject.toml's comment for the full explanation.


def _unique_email() -> str:
    return f"pg-integration-{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture(scope="module")
async def pg_engine():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"DATABASE_URL is not reachable -- skipping Postgres integration tests ({exc})")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine):
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def pg_client(pg_engine):
    """ASGI client whose get_db resolves to THIS module's Postgres engine
    -- same real database as the app would use, but isolated from the
    event-loop-binding issue a shared singleton would hit under pytest."""
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


async def test_migrations_created_expected_tables(pg_engine):
    async with pg_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
        )
        tables = {row[0] for row in result}

    assert {
        "users", "oauth_accounts", "sessions", "password_reset_tokens", "email_verification_tokens",
        "two_factor_recovery_codes", "account_restore_tokens", "two_factor_lockout_recovery_tokens",
        "consent_reactivation_tokens", "alembic_version",
    } <= tables


async def test_every_application_table_has_row_level_security_enabled(pg_engine):
    """
    Partie 1.3.5 -- a regression guard, not a functional isolation test:
    see docs/AUTH_BACKEND_SETUP.md's Row Level Security section for why.
    Every table this app creates has had RLS enabled since migration
    0002 (the earliest tables) and inline in every migration since 0014
    -- this fails loudly if a future migration ever forgets that line,
    rather than the gap going unnoticed because it changes nothing
    observable in this app's own behavior (see the test below for why).
    """
    async with pg_engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT c.relname, c.relrowsecurity
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname != 'alembic_version'
        """))
        rls_enabled_by_table = dict(result.fetchall())

    assert rls_enabled_by_table, "expected at least one application table"
    tables_missing_rls = {table for table, enabled in rls_enabled_by_table.items() if not enabled}
    assert not tables_missing_rls, f"tables with RLS NOT enabled: {sorted(tables_missing_rls)}"


async def test_no_rls_policies_exist_because_none_are_needed_yet(pg_engine):
    """Companion to the test above: RLS enabled with ZERO policies means
    Postgres's default-deny applies to every non-bypassing role (see
    migration 0002's own docstring) -- confirms that's still literally
    true, not just assumed. Adding real per-organization policies here
    would only matter once something other than this app's own
    BYPASSRLS connection queries these tables directly (a future
    Supabase PostgREST/client-SDK exposure) -- see the next test."""
    async with pg_engine.connect() as conn:
        result = await conn.execute(text("SELECT count(*) FROM pg_policies WHERE schemaname = 'public'"))
        policy_count = result.scalar()

    assert policy_count == 0


async def test_the_apps_own_role_bypasses_rls(pg_engine):
    """
    Documents, and would catch a silent change to, the exact fact that
    makes the two tests above "defense-in-depth for OTHER roles" rather
    than "real isolation for this app": the app's own connection
    (`postgres`) has BYPASSRLS, so RLS enabled with zero policies is
    currently a complete no-op for every query this application makes.
    Real, functional per-organization isolation today is 100%
    application-layer (`require_org_member` and its whole family,
    `api/security/organizations.py` onward, extensively tested
    elsewhere in this suite) -- if this test ever starts failing because
    the connection role changed, that is exactly the moment real RLS
    policies would need to exist for the app to keep working at all
    (Postgres denies everything by default to a non-bypassing role
    against a table with RLS enabled and no matching policy)."""
    async with pg_engine.connect() as conn:
        result = await conn.execute(text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user"))
        bypasses_rls = result.scalar()

    assert bypasses_rls is True


async def test_unique_email_constraint_enforced_by_postgres(pg_session):
    email = _unique_email()
    pg_session.add(User(email=email, hashed_password="irrelevant-for-this-test"))
    await pg_session.commit()

    try:
        pg_session.add(User(email=email, hashed_password="also-irrelevant"))
        with pytest.raises(IntegrityError):
            await pg_session.commit()
    finally:
        await pg_session.rollback()
        await pg_session.execute(delete(User).where(User.email == email))
        await pg_session.commit()


async def test_cascade_delete_removes_related_rows(pg_session):
    email = _unique_email()
    user = User(email=email, hashed_password="irrelevant")
    pg_session.add(user)
    await pg_session.flush()
    user_id = user.id

    pg_session.add(SessionModel(
        user_id=user_id, refresh_token_hash=uuid.uuid4().hex,
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
    ))
    pg_session.add(OAuthAccount(user_id=user_id, provider=OAuthProvider.google, provider_account_id=uuid.uuid4().hex))
    pg_session.add(EmailVerificationToken(
        user_id=user_id, code_hash="irrelevant",
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10),
    ))
    pg_session.add(TwoFactorRecoveryCode(user_id=user_id, code_hash="irrelevant"))
    pg_session.add(AccountRestoreToken(
        user_id=user_id, token_hash=uuid.uuid4().hex,
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
    ))
    pg_session.add(TwoFactorLockoutRecoveryToken(
        user_id=user_id, token_hash=uuid.uuid4().hex,
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
    ))
    pg_session.add(ConsentReactivationToken(
        user_id=user_id, token_hash=uuid.uuid4().hex,
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
    ))
    pg_session.add(RevokedAccessToken(
        user_id=user_id, jti=str(uuid.uuid4()),
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15),
    ))
    await pg_session.commit()

    await pg_session.execute(delete(User).where(User.id == user_id))
    await pg_session.commit()

    remaining_sessions = await pg_session.scalar(select(SessionModel).where(SessionModel.user_id == user_id))
    remaining_oauth = await pg_session.scalar(select(OAuthAccount).where(OAuthAccount.user_id == user_id))
    remaining_tokens = await pg_session.scalar(select(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id))
    remaining_recovery_codes = await pg_session.scalar(select(TwoFactorRecoveryCode).where(TwoFactorRecoveryCode.user_id == user_id))
    remaining_restore_tokens = await pg_session.scalar(select(AccountRestoreToken).where(AccountRestoreToken.user_id == user_id))
    remaining_lockout_tokens = await pg_session.scalar(select(TwoFactorLockoutRecoveryToken).where(TwoFactorLockoutRecoveryToken.user_id == user_id))
    remaining_consent_tokens = await pg_session.scalar(select(ConsentReactivationToken).where(ConsentReactivationToken.user_id == user_id))
    remaining_revoked_tokens = await pg_session.scalar(select(RevokedAccessToken).where(RevokedAccessToken.user_id == user_id))

    assert remaining_sessions is None
    assert remaining_oauth is None
    assert remaining_tokens is None
    assert remaining_recovery_codes is None
    assert remaining_restore_tokens is None
    assert remaining_consent_tokens is None
    assert remaining_lockout_tokens is None
    assert remaining_revoked_tokens is None


async def test_deleting_an_organization_cascades_to_its_memberships(pg_session):
    """Etape 1.2.2: api/routers/organizations.py's delete_organization
    uses a Core bulk DELETE (delete(Organization).where(...)), not
    session.delete() -- so no ORM-level cascade applies, only the
    database's own ON DELETE CASCADE (the Alembic migration) does. SQLite
    doesn't enforce foreign keys by default, so this can only be proven
    against real Postgres -- see this file's own module docstring."""
    owner_email = _unique_email()
    owner = User(email=owner_email, hashed_password="irrelevant")
    pg_session.add(owner)
    await pg_session.flush()

    organization = Organization(name="Cascade Test Org", slug=f"cascade-test-{uuid.uuid4().hex[:8]}")
    pg_session.add(organization)
    await pg_session.flush()
    org_id = organization.id
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=owner.id, role=OrganizationRole.owner))
    await pg_session.commit()

    try:
        await pg_session.execute(delete(Organization).where(Organization.id == org_id))
        await pg_session.commit()

        remaining_membership = await pg_session.scalar(
            select(OrganizationMember).where(OrganizationMember.organization_id == org_id)
        )
        assert remaining_membership is None
    finally:
        await pg_session.execute(delete(User).where(User.id == owner.id))
        await pg_session.commit()


async def test_deleting_an_organization_cascades_to_its_workspaces(pg_session):
    """Etape 1.2.4: same reasoning as
    test_deleting_an_organization_cascades_to_its_memberships above --
    delete_organization is a Core bulk DELETE, so only the database's own
    ON DELETE CASCADE (api/alembic/versions/0015_workspaces.py) removes
    the organization's workspaces, which SQLite won't enforce."""
    owner_email = _unique_email()
    owner = User(email=owner_email, hashed_password="irrelevant")
    pg_session.add(owner)
    await pg_session.flush()

    organization = Organization(name="Workspace Cascade Test Org", slug=f"ws-cascade-test-{uuid.uuid4().hex[:8]}")
    pg_session.add(organization)
    await pg_session.flush()
    org_id = organization.id
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=owner.id, role=OrganizationRole.owner))
    pg_session.add(Workspace(organization_id=org_id, name="Cascade Test Workspace", created_by=owner.id))
    await pg_session.commit()

    try:
        await pg_session.execute(delete(Organization).where(Organization.id == org_id))
        await pg_session.commit()

        remaining_workspace = await pg_session.scalar(
            select(Workspace).where(Workspace.organization_id == org_id)
        )
        assert remaining_workspace is None
    finally:
        await pg_session.execute(delete(User).where(User.id == owner.id))
        await pg_session.commit()


async def test_deleting_an_organization_cascades_to_its_resource_permissions(pg_session):
    """Etape 1.2.8: same reasoning as the two cascade tests above --
    api/routers/organizations.py's delete_organization is a Core bulk
    DELETE, so only the database's own ON DELETE CASCADE
    (api/alembic/versions/0017_resource_permissions.py) removes the
    organization's granular grants, which SQLite won't enforce."""
    owner_email = _unique_email()
    owner = User(email=owner_email, hashed_password="irrelevant")
    grantee_email = _unique_email()
    grantee = User(email=grantee_email, hashed_password="irrelevant")
    pg_session.add_all([owner, grantee])
    await pg_session.flush()

    organization = Organization(name="Permission Cascade Test Org", slug=f"perm-cascade-test-{uuid.uuid4().hex[:8]}")
    pg_session.add(organization)
    await pg_session.flush()
    org_id = organization.id
    workspace = Workspace(organization_id=org_id, name="Cascade Test Workspace", created_by=owner.id)
    pg_session.add(workspace)
    await pg_session.flush()
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=owner.id, role=OrganizationRole.owner))
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=grantee.id, role=OrganizationRole.viewer))
    pg_session.add(ResourcePermission(
        organization_id=org_id, resource_type="workspace", resource_id=workspace.id, user_id=grantee.id,
        action="update", granted_by=owner.id,
    ))
    await pg_session.commit()

    try:
        await pg_session.execute(delete(Organization).where(Organization.id == org_id))
        await pg_session.commit()

        remaining_permission = await pg_session.scalar(
            select(ResourcePermission).where(ResourcePermission.organization_id == org_id)
        )
        assert remaining_permission is None
    finally:
        await pg_session.execute(delete(User).where(User.id.in_([owner.id, grantee.id])))
        await pg_session.commit()


async def test_deleting_an_organization_cascades_to_its_teams_and_team_members(pg_session):
    """Partie 1.3.3: same reasoning as the cascade tests above --
    delete_organization is a Core bulk DELETE, so only the database's
    own ON DELETE CASCADE (api/alembic/versions/0018_teams.py) removes
    the organization's teams AND, transitively, their team_members rows,
    which SQLite won't enforce."""
    owner_email = _unique_email()
    owner = User(email=owner_email, hashed_password="irrelevant")
    pg_session.add(owner)
    await pg_session.flush()

    organization = Organization(name="Team Cascade Test Org", slug=f"team-cascade-test-{uuid.uuid4().hex[:8]}")
    pg_session.add(organization)
    await pg_session.flush()
    org_id = organization.id
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=owner.id, role=OrganizationRole.owner))
    team = Team(organization_id=org_id, name="Cascade Test Team", created_by=owner.id)
    pg_session.add(team)
    await pg_session.flush()
    team_id = team.id
    pg_session.add(TeamMember(team_id=team_id, user_id=owner.id, role=TeamRole.admin))
    await pg_session.commit()

    try:
        await pg_session.execute(delete(Organization).where(Organization.id == org_id))
        await pg_session.commit()

        remaining_team = await pg_session.scalar(select(Team).where(Team.id == team_id))
        remaining_team_member = await pg_session.scalar(select(TeamMember).where(TeamMember.team_id == team_id))
        assert remaining_team is None
        assert remaining_team_member is None
    finally:
        await pg_session.execute(delete(User).where(User.id == owner.id))
        await pg_session.commit()


async def test_deleting_an_organization_cascades_to_its_invitations(pg_session):
    """Partie 1.3.4: same reasoning as the cascade tests above --
    delete_organization is a Core bulk DELETE, so only the database's
    own ON DELETE CASCADE (api/alembic/versions/0020_invitations.py)
    removes the organization's pending invitations, which SQLite won't
    enforce."""
    from api.security.hashing import hash_token

    owner_email = _unique_email()
    owner = User(email=owner_email, hashed_password="irrelevant")
    pg_session.add(owner)
    await pg_session.flush()

    organization = Organization(name="Invitation Cascade Test Org", slug=f"invite-cascade-test-{uuid.uuid4().hex[:8]}")
    pg_session.add(organization)
    await pg_session.flush()
    org_id = organization.id
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=owner.id, role=OrganizationRole.owner))
    pg_session.add(Invitation(
        organization_id=org_id, email=_unique_email(), role=OrganizationRole.member, invited_by=owner.id,
        token_hash=hash_token(f"cascade-test-token-{uuid.uuid4().hex}"),
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7),
    ))
    await pg_session.commit()

    try:
        await pg_session.execute(delete(Organization).where(Organization.id == org_id))
        await pg_session.commit()

        remaining_invitation = await pg_session.scalar(select(Invitation).where(Invitation.organization_id == org_id))
        assert remaining_invitation is None
    finally:
        await pg_session.execute(delete(User).where(User.id == owner.id))
        await pg_session.commit()


async def test_deleting_an_organization_cascades_to_its_quota(pg_session):
    """Partie 1.3.6: same reasoning as the cascade tests above --
    delete_organization is a Core bulk DELETE, so only the database's
    own ON DELETE CASCADE (api/alembic/versions/0021_organization_quotas.py)
    removes the organization's quota row, which SQLite won't enforce."""
    owner_email = _unique_email()
    owner = User(email=owner_email, hashed_password="irrelevant")
    pg_session.add(owner)
    await pg_session.flush()

    organization = Organization(name="Quota Cascade Test Org", slug=f"quota-cascade-test-{uuid.uuid4().hex[:8]}")
    pg_session.add(organization)
    await pg_session.flush()
    org_id = organization.id
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=owner.id, role=OrganizationRole.owner))
    pg_session.add(OrganizationQuota(
        organization_id=org_id, max_users=10, max_workspaces=5, max_teams=10, max_documents=1000,
        max_storage_mb=1024, max_requests_per_month=10000, max_requests_per_day=500, max_api_calls=5000,
        max_agents=10, max_kb_size_mb=512,
    ))
    await pg_session.commit()

    try:
        await pg_session.execute(delete(Organization).where(Organization.id == org_id))
        await pg_session.commit()

        remaining_quota = await pg_session.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == org_id))
        assert remaining_quota is None
    finally:
        await pg_session.execute(delete(User).where(User.id == owner.id))
        await pg_session.commit()


async def test_creating_an_organization_creates_its_quota_row_in_the_same_transaction(pg_client, pg_engine):
    """Real end-to-end proof against Postgres (not SQLite) that
    create_organization_with_owner's three inserts -- organization,
    founding Owner membership, default quota -- all land together, via
    the real HTTP endpoint."""
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    email = _unique_email()
    org_id = None

    try:
        register_response = await pg_client.post(
            "/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True},
        )
        assert register_response.status_code == 201

        async with session_factory() as session:
            user = await session.scalar(select(User).where(User.email == email))
            membership = await session.scalar(select(OrganizationMember).where(OrganizationMember.user_id == user.id))
            org_id = membership.organization_id
            quota = await session.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == org_id))
            assert quota is not None
            assert quota.max_users == settings.QUOTA_DEFAULT_MAX_USERS
    finally:
        async with session_factory() as session:
            # Delete the auto-created default organization FIRST -- it
            # cascades to the membership and quota rows; the user alone
            # has no FK to the organization, so deleting just the user
            # would leave both orphaned.
            if org_id is not None:
                await session.execute(delete(Organization).where(Organization.id == org_id))
            user = await session.scalar(select(User).where(User.email == email))
            if user is not None:
                await session.execute(delete(User).where(User.id == user.id))
            await session.commit()


async def test_new_membership_columns_get_the_documented_defaults_on_real_postgres(pg_client, pg_engine):
    """Partie 1.3.7: proves migration 0022's `server_default` values
    (used for backfilling pre-existing rows) and
    api/models/organization.py's Python-level `default=` (used for new
    rows the ORM inserts, which never go through server_default at all)
    actually agree -- against a REAL row, created through the real
    registration endpoint, not asserted from the model definition alone."""
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    email = _unique_email()
    org_id = None

    try:
        register_response = await pg_client.post(
            "/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True},
        )
        assert register_response.status_code == 201

        async with session_factory() as session:
            user = await session.scalar(select(User).where(User.email == email))
            membership = await session.scalar(select(OrganizationMember).where(OrganizationMember.user_id == user.id))
            org_id = membership.organization_id
            assert membership.daily_request_limit is None
            assert membership.max_documents is None
            assert membership.max_conversations is None
            assert membership.can_create_workspaces is True
            assert membership.can_create_teams is True
            assert membership.can_invite_members is False
    finally:
        async with session_factory() as session:
            if org_id is not None:
                await session.execute(delete(Organization).where(Organization.id == org_id))
            user = await session.scalar(select(User).where(User.email == email))
            if user is not None:
                await session.execute(delete(User).where(User.id == user.id))
            await session.commit()


async def test_deleting_an_organization_cascades_to_its_usage_rows(pg_session):
    """Partie 1.3.8: same reasoning as the other cascade tests in this
    file -- delete_organization is a Core bulk DELETE, so only the
    database's own ON DELETE CASCADE
    (api/alembic/versions/0023_organization_usage.py) removes an
    organization's usage rows, which SQLite won't enforce."""
    owner_email = _unique_email()
    owner = User(email=owner_email, hashed_password="irrelevant")
    pg_session.add(owner)
    await pg_session.flush()

    organization = Organization(name="Usage Cascade Test Org", slug=f"usage-cascade-test-{uuid.uuid4().hex[:8]}")
    pg_session.add(organization)
    await pg_session.flush()
    org_id = organization.id
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=owner.id, role=OrganizationRole.owner))
    pg_session.add(OrganizationUsage(organization_id=org_id, date=dt.date.today(), metric="workspaces_created", value=1))
    pg_session.add(OrganizationUsageDetail(organization_id=org_id, user_id=owner.id, metric="workspaces_created", value=1))
    await pg_session.commit()

    try:
        await pg_session.execute(delete(Organization).where(Organization.id == org_id))
        await pg_session.commit()

        remaining_usage = await pg_session.scalar(select(OrganizationUsage).where(OrganizationUsage.organization_id == org_id))
        remaining_detail = await pg_session.scalar(select(OrganizationUsageDetail).where(OrganizationUsageDetail.organization_id == org_id))
        assert remaining_usage is None
        assert remaining_detail is None
    finally:
        await pg_session.execute(delete(User).where(User.id == owner.id))
        await pg_session.commit()


async def test_organization_usage_detail_metadata_round_trips_as_json_on_real_postgres(pg_session):
    """Partie 1.3.8: api/models/organization_usage.py's own docstring
    explains why metadata_json uses the generic, cross-dialect sa.JSON
    type rather than postgresql.JSONB -- this proves that choice still
    gets a REAL JSON column on real Postgres (not silently falling back
    to TEXT the way SQLite's fast suite represents it), round-tripping a
    nested dict intact through an actual INSERT/SELECT."""
    owner_email = _unique_email()
    owner = User(email=owner_email, hashed_password="irrelevant")
    pg_session.add(owner)
    await pg_session.flush()

    organization = Organization(name="Usage JSON Test Org", slug=f"usage-json-test-{uuid.uuid4().hex[:8]}")
    pg_session.add(organization)
    await pg_session.flush()
    org_id = organization.id
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=owner.id, role=OrganizationRole.owner))
    detail = OrganizationUsageDetail(
        organization_id=org_id, user_id=owner.id, metric="quota_exceeded", value=1,
        metadata_json={"resource_type": "workspaces", "limit": 0},
    )
    pg_session.add(detail)
    await pg_session.commit()
    detail_id = detail.id

    try:
        column_type = await pg_session.scalar(text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'organization_usage_details' AND column_name = 'metadata_json'"
        ))
        assert column_type == "json"

        reloaded = await pg_session.scalar(select(OrganizationUsageDetail).where(OrganizationUsageDetail.id == detail_id))
        assert reloaded.metadata_json == {"resource_type": "workspaces", "limit": 0}
    finally:
        await pg_session.execute(delete(Organization).where(Organization.id == org_id))
        await pg_session.execute(delete(User).where(User.id == owner.id))
        await pg_session.commit()


async def test_deleting_an_organization_cascades_to_its_settings(pg_session):
    """Partie 1.3.9: same reasoning as the other cascade tests in this
    file -- delete_organization is a Core bulk DELETE, so only the
    database's own ON DELETE CASCADE
    (api/alembic/versions/0024_organization_settings.py) removes an
    organization's settings row, which SQLite won't enforce."""
    owner_email = _unique_email()
    owner = User(email=owner_email, hashed_password="irrelevant")
    pg_session.add(owner)
    await pg_session.flush()

    organization = Organization(name="Settings Cascade Test Org", slug=f"settings-cascade-test-{uuid.uuid4().hex[:8]}")
    pg_session.add(organization)
    await pg_session.flush()
    org_id = organization.id
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=owner.id, role=OrganizationRole.owner))
    pg_session.add(OrganizationSettings(organization_id=org_id, settings={"chunk_size": 1024}))
    await pg_session.commit()

    try:
        await pg_session.execute(delete(Organization).where(Organization.id == org_id))
        await pg_session.commit()

        remaining_settings = await pg_session.scalar(select(OrganizationSettings).where(OrganizationSettings.organization_id == org_id))
        assert remaining_settings is None
    finally:
        await pg_session.execute(delete(User).where(User.id == owner.id))
        await pg_session.commit()


async def test_creating_an_organization_creates_its_settings_row_in_the_same_transaction(pg_client, pg_engine):
    """Real end-to-end proof against Postgres (not SQLite) that
    create_organization_with_owner's inserts -- organization, founding
    Owner membership, default quota, default settings -- all land
    together, via the real HTTP endpoint."""
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    email = _unique_email()
    org_id = None

    try:
        register_response = await pg_client.post(
            "/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True},
        )
        assert register_response.status_code == 201

        async with session_factory() as session:
            user = await session.scalar(select(User).where(User.email == email))
            membership = await session.scalar(select(OrganizationMember).where(OrganizationMember.user_id == user.id))
            org_id = membership.organization_id
            settings_row = await session.scalar(select(OrganizationSettings).where(OrganizationSettings.organization_id == org_id))
            assert settings_row is not None
            assert settings_row.settings == {}
    finally:
        async with session_factory() as session:
            if org_id is not None:
                await session.execute(delete(Organization).where(Organization.id == org_id))
            user = await session.scalar(select(User).where(User.email == email))
            if user is not None:
                await session.execute(delete(User).where(User.id == user.id))
            await session.commit()


async def test_deleting_an_organization_cascades_to_its_branding(pg_session):
    """Partie 1.3.10: same reasoning as the other cascade tests in this
    file -- delete_organization is a Core bulk DELETE, so only the
    database's own ON DELETE CASCADE
    (api/alembic/versions/0025_organization_branding.py) removes an
    organization's branding row, which SQLite won't enforce."""
    owner_email = _unique_email()
    owner = User(email=owner_email, hashed_password="irrelevant")
    pg_session.add(owner)
    await pg_session.flush()

    organization = Organization(name="Branding Cascade Test Org", slug=f"branding-cascade-test-{uuid.uuid4().hex[:8]}")
    pg_session.add(organization)
    await pg_session.flush()
    org_id = organization.id
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=owner.id, role=OrganizationRole.owner))
    pg_session.add(OrganizationBranding(organization_id=org_id, brand_name="Cascade Co"))
    await pg_session.commit()

    try:
        await pg_session.execute(delete(Organization).where(Organization.id == org_id))
        await pg_session.commit()

        remaining_branding = await pg_session.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id == org_id))
        assert remaining_branding is None
    finally:
        await pg_session.execute(delete(User).where(User.id == owner.id))
        await pg_session.commit()


async def test_creating_an_organization_creates_its_branding_row_with_documented_defaults(pg_client, pg_engine):
    """Real end-to-end proof against Postgres (not SQLite) that
    create_organization_with_owner's inserts -- organization, founding
    Owner membership, default quota, default settings, default branding
    -- all land together, via the real HTTP endpoint, and that the
    server_default color values (migration 0025) actually match the
    Python-level defaults (api/models/organization_branding.py)."""
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    email = _unique_email()
    org_id = None

    try:
        register_response = await pg_client.post(
            "/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True},
        )
        assert register_response.status_code == 201

        async with session_factory() as session:
            user = await session.scalar(select(User).where(User.email == email))
            membership = await session.scalar(select(OrganizationMember).where(OrganizationMember.user_id == user.id))
            org_id = membership.organization_id
            branding = await session.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id == org_id))
            assert branding is not None
            assert branding.primary_color == "#2563eb"
            assert branding.secondary_color == "#1e293b"
            assert branding.accent_color == "#f59e0b"
            assert branding.font_family == "Inter"
            assert branding.logo_url is None
            assert branding.brand_name is None
    finally:
        async with session_factory() as session:
            if org_id is not None:
                await session.execute(delete(Organization).where(Organization.id == org_id))
            user = await session.scalar(select(User).where(User.email == email))
            if user is not None:
                await session.execute(delete(User).where(User.id == user.id))
            await session.commit()


async def test_deleting_an_organization_cascades_to_its_custom_domains(pg_session):
    """Partie 1.4.1: same reasoning as the other cascade tests in this
    file -- delete_organization is a Core bulk DELETE, so only the
    database's own ON DELETE CASCADE
    (api/alembic/versions/0026_custom_domains.py) removes an
    organization's custom domain rows, which SQLite won't enforce."""
    owner_email = _unique_email()
    owner = User(email=owner_email, hashed_password="irrelevant")
    pg_session.add(owner)
    await pg_session.flush()

    organization = Organization(name="Custom Domain Cascade Test Org", slug=f"domain-cascade-test-{uuid.uuid4().hex[:8]}")
    pg_session.add(organization)
    await pg_session.flush()
    org_id = organization.id
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=owner.id, role=OrganizationRole.owner))
    pg_session.add(CustomDomain(
        organization_id=org_id, domain=f"app.cascade-test-{uuid.uuid4().hex[:8]}.example", verification_token="irrelevant-token",
    ))
    await pg_session.commit()

    try:
        await pg_session.execute(delete(Organization).where(Organization.id == org_id))
        await pg_session.commit()

        remaining_domain = await pg_session.scalar(select(CustomDomain).where(CustomDomain.organization_id == org_id))
        assert remaining_domain is None
    finally:
        await pg_session.execute(delete(User).where(User.id == owner.id))
        await pg_session.commit()


async def test_deleting_an_organization_cascades_through_custom_domains_to_ssl_certificates(pg_session):
    """Partie 1.4.3: a TWO-LEVEL cascade -- organizations -> custom_domains
    (Partie 1.4.1's FK) -> ssl_certificates (this step's own FK, to
    custom_domains.domain rather than .id). Deleting the organization
    must remove both, which SQLite's fast suite won't enforce either way."""
    owner_email = _unique_email()
    owner = User(email=owner_email, hashed_password="irrelevant")
    pg_session.add(owner)
    await pg_session.flush()

    organization = Organization(name="SSL Cascade Test Org", slug=f"ssl-cascade-test-{uuid.uuid4().hex[:8]}")
    pg_session.add(organization)
    await pg_session.flush()
    org_id = organization.id
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=owner.id, role=OrganizationRole.owner))
    domain_str = f"app.ssl-cascade-test-{uuid.uuid4().hex[:8]}.example"
    pg_session.add(CustomDomain(organization_id=org_id, domain=domain_str, verification_token="irrelevant-token"))
    await pg_session.flush()
    pg_session.add(SSLCertificate(domain=domain_str, key_pem_encrypted=encrypt_secret("fake-key-placeholder")))
    await pg_session.commit()

    try:
        await pg_session.execute(delete(Organization).where(Organization.id == org_id))
        await pg_session.commit()

        remaining_domain = await pg_session.scalar(select(CustomDomain).where(CustomDomain.organization_id == org_id))
        remaining_cert = await pg_session.scalar(select(SSLCertificate).where(SSLCertificate.domain == domain_str))
        assert remaining_domain is None
        assert remaining_cert is None
    finally:
        await pg_session.execute(delete(User).where(User.id == owner.id))
        await pg_session.commit()


async def test_deleting_a_document_cascades_to_its_chunks(pg_session):
    """Partie 2.1.1: same reasoning as the other cascade tests in this
    file -- api/routers/documents.py's delete_document is a Core bulk
    DELETE, so only the database's own ON DELETE CASCADE
    (api/alembic/versions/0031_documents.py) removes a document's
    chunks, which SQLite won't enforce."""
    owner_email = _unique_email()
    owner = User(email=owner_email, hashed_password="irrelevant")
    pg_session.add(owner)
    await pg_session.flush()

    organization = Organization(name="Document Cascade Test Org", slug=f"document-cascade-test-{uuid.uuid4().hex[:8]}")
    pg_session.add(organization)
    await pg_session.flush()
    org_id = organization.id
    pg_session.add(OrganizationMember(organization_id=org_id, user_id=owner.id, role=OrganizationRole.owner))
    document = Document(
        organization_id=org_id, name="test.pdf", file_key="documents/irrelevant/test.pdf",
        file_size=1024, file_type="application/pdf", status=DocumentStatus.completed.value, created_by=owner.id,
    )
    pg_session.add(document)
    await pg_session.flush()
    document_id = document.id
    pg_session.add(DocumentChunk(document_id=document_id, organization_id=org_id, content="chunk content", embedding=[0.1, 0.2, 0.3]))
    await pg_session.commit()

    try:
        await pg_session.execute(delete(Document).where(Document.id == document_id))
        await pg_session.commit()

        remaining_chunk = await pg_session.scalar(select(DocumentChunk).where(DocumentChunk.document_id == document_id))
        assert remaining_chunk is None
    finally:
        await pg_session.execute(delete(Organization).where(Organization.id == org_id))
        await pg_session.execute(delete(User).where(User.id == owner.id))
        await pg_session.commit()


async def test_full_auth_cycle_against_real_postgres(pg_client, pg_engine):
    """register -> login -> refresh -> logout, through the real ASGI app,
    against real Postgres (via pg_client's get_db override, not SQLite)."""
    email = _unique_email()

    try:
        register = await pg_client.post("/auth/register", json={
            "email": email, "password": "correct-horse-battery-staple",
            "full_name": "PG Integration", "accept_terms": True,
        })
        assert register.status_code == 201

        login = await pg_client.post("/auth/login", json={"email": email, "password": "correct-horse-battery-staple"})
        assert login.status_code == 200

        # /auth/refresh and /auth/logout are CSRF-protected (1.1.16) --
        # echo back the csrf_token cookie set alongside the refresh
        # cookie at login, same as a real browser's JS would.
        csrf_headers = {"X-CSRF-Token": pg_client.cookies.get("csrf_token") or ""}

        refresh = await pg_client.post("/auth/refresh", headers=csrf_headers)
        assert refresh.status_code == 200

        csrf_headers = {"X-CSRF-Token": pg_client.cookies.get("csrf_token") or ""}  # refresh rotated it
        logout = await pg_client.post("/auth/logout", headers=csrf_headers)
        assert logout.status_code == 200
    finally:
        async with pg_engine.connect() as conn:
            await conn.execute(delete(User).where(User.email == email))
            await conn.commit()
