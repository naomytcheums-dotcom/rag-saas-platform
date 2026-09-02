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
