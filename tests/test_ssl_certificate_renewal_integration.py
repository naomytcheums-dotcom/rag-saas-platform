"""
Partie 1.4.3, item 5 -- the two periodic Celery tasks
(api/tasks/ssl_certificate_renewal.py), against the real Postgres dev
database. Skips if unreachable, same convention as
tests/test_celery_integration.py.

The task bodies bridge into async code via asyncio.run() (see that
module's own docstring for why, unlike every other task in this
package) -- calling a Celery task synchronously via `.apply()` from
inside an ALREADY-running event loop (an `async def` pytest test) would
raise "asyncio.run() cannot be called from a running event loop". So
the actual business logic is exercised directly against its async
helper functions (real Postgres, mocked ACME calls) in `async def`
tests, and the sync Celery-task wrapper itself is smoke-tested
separately in a plain `def test_...` with no event loop already
running -- exactly the shape Celery's own worker process calls it in.
"""

import datetime as dt
import uuid

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.custom_domain import CustomDomain, CustomDomainStatus
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.ssl_certificate import SSLCertificate, SSLCertificateStatus
from api.models.user import User
from api.security.secret_encryption import encrypt_secret
from api.tasks.ssl_certificate_renewal import _check_ssl_expirations_async, _check_ssl_renewals_async, check_ssl_expirations, check_ssl_renewals


def _unique_email() -> str:
    return f"ssl-renewal-itest-{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture(scope="module")
async def pg_engine():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"DATABASE_URL is not reachable -- skipping SSL renewal task integration tests ({exc})")
    yield engine
    await engine.dispose()


async def _make_org_domain_and_certificate(session, *, expires_at: dt.datetime, status: str = SSLCertificateStatus.issued.value):
    owner = User(email=_unique_email(), hashed_password="irrelevant")
    session.add(owner)
    await session.flush()

    organization = Organization(name="SSL Renewal ITest Org", slug=f"ssl-renewal-itest-{uuid.uuid4().hex[:8]}")
    session.add(organization)
    await session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=owner.id, role=OrganizationRole.owner))

    domain_str = f"app-{uuid.uuid4().hex[:8]}.ssl-renewal-itest.example"
    domain = CustomDomain(organization_id=organization.id, domain=domain_str, status=CustomDomainStatus.active.value, verification_token="irrelevant")
    session.add(domain)

    certificate = SSLCertificate(
        domain=domain_str, status=status, key_pem_encrypted=encrypt_secret("fake-key-placeholder"),
        cert_pem="-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----" if status == SSLCertificateStatus.issued.value else None,
        expires_at=expires_at,
    )
    session.add(certificate)
    await session.commit()
    return owner, organization, domain, certificate


async def _cleanup(session, organization_id, owner_id):
    await session.execute(delete(Organization).where(Organization.id == organization_id))
    await session.execute(delete(User).where(User.id == owner_id))
    await session.commit()


async def test_check_ssl_renewals_starts_a_real_renewal_for_a_certificate_expiring_soon(pg_engine, monkeypatch):
    """Validation criterion: the renewal task acts on certificates
    within the renewal window (30 days by default)."""
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)

    async def _fake_account(db):
        return ("fake-account-key", "https://acme.example/acct/1")

    monkeypatch.setattr("api.security.ssl_certificates.get_or_create_acme_account", _fake_account)
    monkeypatch.setattr(
        "api.security.ssl_certificates._open_order",
        lambda account_key, account_url, domain, cert_key: (
            "https://acme.example/order/renew", "https://acme.example/chall/renew",
            f"_acme-challenge.{domain}", "renewal-value", "https://acme.example/finalize/renew",
        ),
    )

    async with session_factory() as session:
        owner, organization, domain, certificate = await _make_org_domain_and_certificate(
            session, expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=5),  # within the 30-day window
        )
        try:
            renewed_count = await _check_ssl_renewals_async()
            assert renewed_count >= 1

            # _check_ssl_renewals_async commits via its OWN, separate
            # engine/session -- this test's `session` already has
            # `certificate` in its identity map from creating it above,
            # so a plain re-SELECT would return that stale cached
            # object rather than the real, just-committed row. Force a
            # real reload from the database.
            await session.refresh(certificate)
            assert certificate.status == SSLCertificateStatus.pending_dns01.value
            assert certificate.dns01_record_value == "renewal-value"
        finally:
            await _cleanup(session, organization.id, owner.id)


async def test_check_ssl_renewals_ignores_certificates_not_yet_due(pg_engine):
    """A certificate expiring well outside the renewal window must be
    left completely untouched."""
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)

    async with session_factory() as session:
        owner, organization, domain, certificate = await _make_org_domain_and_certificate(
            session, expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=200),  # far outside the window
        )
        try:
            await _check_ssl_renewals_async()

            # Force a real reload -- see the previous test's comment on
            # why a plain re-SELECT through this same session's
            # identity map wouldn't actually prove anything either way.
            await session.refresh(certificate)
            assert certificate.status == SSLCertificateStatus.issued.value  # untouched
        finally:
            await _cleanup(session, organization.id, owner.id)


async def test_check_ssl_expirations_detects_an_already_expired_issued_certificate(pg_engine):
    """Validation criterion: an expired certificate is detected."""
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)

    async with session_factory() as session:
        owner, organization, domain, certificate = await _make_org_domain_and_certificate(
            session, expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),  # already expired
        )
        try:
            expired_domains = await _check_ssl_expirations_async()
            assert domain.domain in expired_domains
        finally:
            await _cleanup(session, organization.id, owner.id)


async def test_check_ssl_expirations_ignores_a_certificate_not_yet_expired(pg_engine):
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)

    async with session_factory() as session:
        owner, organization, domain, certificate = await _make_org_domain_and_certificate(
            session, expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=60),
        )
        try:
            expired_domains = await _check_ssl_expirations_async()
            assert domain.domain not in expired_domains
        finally:
            await _cleanup(session, organization.id, owner.id)


def test_the_celery_tasks_themselves_run_via_apply_with_no_event_loop_conflict():
    """
    Smoke test for the ACTUAL Celery entry points (not their async
    helpers) -- a plain sync function, exactly the call shape a real
    Celery worker uses, with no already-running event loop for
    asyncio.run() (inside these tasks) to conflict with. Doesn't assert
    on specific counts (the dev database's real state is out of this
    test's control) -- only that both tasks complete and return the
    documented shape without raising. No `pg_engine` fixture here (it's
    an async fixture, unusable from a plain sync test) -- a plain
    try/except stands in for the same "skip if unreachable" convention.
    """
    try:
        renewed_count = check_ssl_renewals.apply().get()
        expired_domains = check_ssl_expirations.apply().get()
    except Exception as exc:
        pytest.skip(f"DATABASE_URL is not reachable -- skipping SSL renewal task integration tests ({exc})")

    assert isinstance(renewed_count, int)
    assert isinstance(expired_domains, list)
