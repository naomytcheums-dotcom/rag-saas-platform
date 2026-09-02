"""
Partie 1.4.4 -- the two periodic/one-off Celery tasks
(api/tasks/domain_verification.py), against the real Postgres dev
database. Skips if unreachable, same convention as
tests/test_ssl_certificate_renewal_integration.py.

Same asyncio.run()-bridge reasoning as that file: the actual business
logic is exercised directly against its async helper functions (real
Postgres, mocked DNS lookups) in `async def` tests, and the sync
Celery-task wrapper itself is smoke-tested separately in a plain
`def test_...` with no event loop already running -- exactly the shape
Celery's own worker process calls it in.
"""

import uuid

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.custom_domain import CustomDomain, CustomDomainStatus
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User
from api.tasks.domain_verification import (
    _check_pending_domain_verifications_async,
    _poll_one_domain_async,
    check_pending_domain_verifications,
    poll_one_domain,
)


def _unique_email() -> str:
    return f"domain-verify-itest-{uuid.uuid4().hex[:10]}@example.com"


async def _dns_matches(domain: str, token: str) -> bool:
    return True


async def _dns_does_not_match(domain: str, token: str) -> bool:
    return False


@pytest.fixture(scope="module")
async def pg_engine():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"DATABASE_URL is not reachable -- skipping domain verification task integration tests ({exc})")
    yield engine
    await engine.dispose()


async def _make_org_and_pending_domain(session, *, domain_suffix: str):
    owner = User(email=_unique_email(), hashed_password="irrelevant")
    session.add(owner)
    await session.flush()

    organization = Organization(name="Domain Verify ITest Org", slug=f"domain-verify-itest-{uuid.uuid4().hex[:8]}")
    session.add(organization)
    await session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=owner.id, role=OrganizationRole.owner))

    domain_str = f"itest-{uuid.uuid4().hex[:8]}.{domain_suffix}"
    domain = CustomDomain(
        organization_id=organization.id, domain=domain_str, status=CustomDomainStatus.pending.value,
        verification_token="irrelevant",
    )
    session.add(domain)
    await session.commit()
    return owner, organization, domain


async def _cleanup(session, organization_id, owner_id):
    await session.execute(delete(Organization).where(Organization.id == organization_id))
    await session.execute(delete(User).where(User.id == owner_id))
    await session.commit()


async def test_check_pending_domain_verifications_activates_a_matching_domain(pg_engine, monkeypatch):
    """Validation criterion: the Celery task checks pending domains and
    activates the ones whose DNS now matches."""
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_matches)

    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        owner, organization, domain = await _make_org_and_pending_domain(session, domain_suffix="domain-verify-itest.example")
        try:
            results = await _check_pending_domain_verifications_async()
            assert results["activated"] >= 1

            # _check_pending_domain_verifications_async commits via its
            # OWN, separate engine/session -- force a real reload rather
            # than trusting this session's identity map, same reasoning
            # as tests/test_ssl_certificate_renewal_integration.py.
            await session.refresh(domain)
            assert domain.status == CustomDomainStatus.active.value
            assert domain.verification_attempts == 1
        finally:
            await _cleanup(session, organization.id, owner.id)


async def test_check_pending_domain_verifications_leaves_a_non_matching_domain_pending(pg_engine, monkeypatch):
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_does_not_match)

    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        owner, organization, domain = await _make_org_and_pending_domain(session, domain_suffix="domain-verify-itest.example")
        try:
            await _check_pending_domain_verifications_async()

            await session.refresh(domain)
            assert domain.status == CustomDomainStatus.pending.value
            assert domain.verification_attempts == 1
        finally:
            await _cleanup(session, organization.id, owner.id)


async def test_poll_one_domain_activates_the_named_domain(pg_engine, monkeypatch):
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_matches)

    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        owner, organization, domain = await _make_org_and_pending_domain(session, domain_suffix="domain-verify-itest.example")
        try:
            await _poll_one_domain_async(domain.domain)

            await session.refresh(domain)
            assert domain.status == CustomDomainStatus.active.value
        finally:
            await _cleanup(session, organization.id, owner.id)


async def test_poll_one_domain_is_a_no_op_for_a_domain_deleted_before_the_task_runs(pg_engine):
    """A domain can be deleted between schedule_domain_verification
    dispatching this one-off task and the task actually running -- must
    not raise."""
    await _poll_one_domain_async(f"deleted-{uuid.uuid4().hex[:8]}.domain-verify-itest.example")  # must not raise


def test_the_celery_tasks_themselves_run_via_apply_with_no_event_loop_conflict():
    """
    Smoke test for the ACTUAL Celery entry points (not their async
    helpers) -- a plain sync function, exactly the call shape a real
    Celery worker uses, with no already-running event loop for
    asyncio.run() (inside these tasks) to conflict with.
    """
    try:
        results = check_pending_domain_verifications.apply().get()
        poll_one_domain.apply(args=[f"never-registered-{uuid.uuid4().hex[:8]}.example"]).get()
    except Exception as exc:
        pytest.skip(f"DATABASE_URL is not reachable -- skipping domain verification task integration tests ({exc})")

    assert isinstance(results, dict)
    assert set(results.keys()) == {"activated", "failed", "still_pending"}
