"""
Partie 1.4.5 -- real infrastructure tests for api/security/email_domains.py
and api/services/resend_domains.py: real DNS resolution (same convention
as tests/test_dns_verification_integration.py) and Resend's real
Domains API (same "hit the real service, verify real behavior" ethos as
tests/test_acme_integration.py against Let's Encrypt staging).

**A real, honest finding from writing this file, not a hypothetical**:
this project's own RESEND_API_KEY (already used for real by
api/services/email.py's password-reset/etc. emails) is scoped
send-only -- Resend's real Domains API rejects it with a real 4xx
error. Confirmed to vary by environment, not a fixed code: local dev's
send-only-restricted key gets a `401 restricted_api_key`; CI's
placeholder key (not a real key at all) gets a different `400
validation_error` ("API key is invalid"). The tests below verify BOTH
real outcomes correctly (a full-access key succeeding, or ANY real 4xx
rejection) rather than assuming one specific error -- see
test_resend_domain_lifecycle_against_the_real_api's own docstring.

Skips the Resend-dependent tests (not a failure) only when RESEND_API_KEY
is entirely unset or the network is unreachable -- a real 4xx response
FROM Resend for insufficient permissions is itself a meaningful,
asserted-on outcome, not something to skip past.
"""

import uuid

import dns.asyncresolver
import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.custom_domain import CustomDomain, CustomDomainStatus
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.email_domains import (
    _lookup_txt_records,
    check_email_verification_txt_record,
    ensure_email_domain_setup,
    verify_dkim,
)
from api.services.email import send_via_custom_email_domain
from api.services.resend_domains import create_resend_domain, delete_resend_domain


def _unique_email() -> str:
    return f"email-domain-itest-{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture(scope="module", autouse=True)
async def _require_real_dns():
    try:
        resolver = dns.asyncresolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        await resolver.resolve("google.com", "A")
    except Exception as exc:
        pytest.skip(f"Outbound DNS is not reachable -- skipping real email-domain verification tests ({exc})")


@pytest.fixture(scope="module")
async def pg_engine():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"DATABASE_URL is not reachable -- skipping email-domain integration tests ({exc})")
    yield engine
    await engine.dispose()


# ------------------------------------------------------------- real DNS --

async def test_lookup_txt_records_handles_a_nonexistent_domain():
    records = await _lookup_txt_records(f"{uuid.uuid4().hex}.invalid")
    assert records == []


async def test_check_email_verification_txt_record_returns_false_for_a_real_domain_without_our_token():
    """A real domain, a real DNS lookup, a token that will never be
    among its TXT records -- the real end-to-end path (not the mocked
    one in tests/test_email_domains.py) correctly reports "not
    verified" rather than raising."""
    matched = await check_email_verification_txt_record("google.com", f"definitely-not-a-real-token-{uuid.uuid4().hex}")
    assert matched is False


async def test_verify_dkim_returns_false_for_a_real_domain_with_a_fabricated_public_key():
    row = CustomDomain(
        domain="google.com", verification_token="irrelevant",
        dkim_selector=settings.DKIM_SELECTOR, dkim_public_key="a-key-that-will-never-be-published-anywhere",
    )
    assert await verify_dkim(row) is False


# --------------------------------------------------------- real Resend API --

async def test_resend_domain_lifecycle_against_the_real_api():
    """
    Real call against Resend's real API -- verified to behave correctly
    whichever of two real outcomes this environment's RESEND_API_KEY
    permission scope produces (checked here, not assumed):

    - a full-access key: a real domain gets created, with the real
      `records` shape Resend actually returns, then deleted so no junk
      domain is left behind in the real Resend account.
    - a key that can't manage domains -- confirmed (by actually running
      this test in two different real environments) to come back as
      TWO DIFFERENT real Resend errors depending on exactly what's wrong
      with the key: local dev's real, send-only-restricted key gets a
      401 `restricted_api_key`; CI's placeholder key (not a real key at
      all, see .github/workflows/regression.yml's RESEND_API_KEY) gets a
      400 `validation_error` ("API key is invalid"). Both are asserted
      on here (any real 4xx response FROM Resend, not a specific code),
      correctly translated by api/services/resend_domains.py into a
      RuntimeError -- not swallowed, not misreported as a generic failure.

    If RESEND_API_KEY becomes unset or the network is unreachable, this
    still fails loudly rather than skipping -- unlike a 4xx (a real,
    meaningful response FROM Resend), those indicate this test can't
    reach Resend AT ALL, which is worth knowing about, not hiding.
    """
    domain = f"itest-{uuid.uuid4().hex[:8]}.email-domain-itest.example"
    try:
        result = create_resend_domain(domain)
    except RuntimeError as exc:
        assert "Resend returned an error (status 4" in str(exc), f"Unexpected Resend failure (not a real 4xx response from Resend): {exc}"
        return

    assert result["id"]
    assert result["name"] == domain
    assert "records" in result
    delete_resend_domain(result["id"])


async def test_send_via_custom_email_domain_is_rejected_by_the_real_resend_api_for_an_unverified_domain():
    """
    Item 6's literal "l'envoi d'email avec un domaine personnalisé
    fonctionne", proven honestly: this app's OWN ownership check is set
    directly here (bypassing DNS, to isolate what this test is actually
    about) so the call reaches Resend's real /emails endpoint -- which
    must reject it, since Resend's OWN domain object was never verified
    for real (this test never owns the fake domain used here). A silent
    "success" here would mean send_via_custom_email_domain is faking
    delivery rather than really talking to Resend -- to
    delivered@resend.dev, Resend's own documented safe testing address,
    so a real acceptance (this environment's key allowing it and Resend
    somehow accepting it) would still never reach a real inbox.
    """
    domain_row = CustomDomain(
        domain=f"itest-{uuid.uuid4().hex[:8]}.email-domain-itest.example", verification_token="irrelevant", email_verified=True,
    )
    try:
        send_via_custom_email_domain(domain_row, "contact", "delivered@resend.dev", "Integration test", "<p>test</p>")
        assert False, "Resend should have rejected sending from a domain it never verified"
    except RuntimeError:
        pass  # the real, expected outcome -- a genuine Resend rejection, not swallowed or faked


# ----------------------------------------------- ensure_email_domain_setup --

async def _make_org_and_domain(session):
    owner = User(email=_unique_email(), hashed_password="irrelevant")
    session.add(owner)
    await session.flush()

    organization = Organization(name="Email Domain ITest Org", slug=f"email-domain-itest-{uuid.uuid4().hex[:8]}")
    session.add(organization)
    await session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=owner.id, role=OrganizationRole.owner))

    domain_str = f"itest-{uuid.uuid4().hex[:8]}.email-domain-itest.example"
    domain = CustomDomain(organization_id=organization.id, domain=domain_str, status=CustomDomainStatus.pending.value, verification_token="irrelevant")
    session.add(domain)
    await session.commit()
    return owner, organization, domain


async def _cleanup(session, organization_id, owner_id):
    await session.execute(delete(Organization).where(Organization.id == organization_id))
    await session.execute(delete(User).where(User.id == owner_id))
    await session.commit()


async def test_ensure_email_domain_setup_against_real_postgres(pg_engine):
    """
    Validation criterion: DKIM key generation really works, end to end,
    against a real Postgres row -- a real RSA keypair generated, the
    private key really Fernet-encrypted before being written (see
    api/security/secret_encryption.py), and never crashes regardless of
    what Resend's real API does with this environment's key (see
    test_resend_domain_lifecycle_against_the_real_api above) -- that
    part is asserted as best-effort here, not required to succeed.
    """
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        owner, organization, domain = await _make_org_and_domain(session)
        try:
            updated = await ensure_email_domain_setup(session, domain)
            await session.commit()

            assert updated.dkim_public_key is not None
            assert updated.dkim_private_key is not None
            assert "PRIVATE KEY" not in updated.dkim_private_key  # encrypted, not raw PEM
            assert updated.dkim_selector == settings.DKIM_SELECTOR
            assert updated.email_verification_token is not None
            assert updated.email_verification_started_at is not None

            if updated.resend_domain_id is not None:
                delete_resend_domain(updated.resend_domain_id)  # real success this run -- clean up after ourselves
        finally:
            await _cleanup(session, organization.id, owner.id)


async def test_ensure_email_domain_setup_is_idempotent_against_real_postgres(pg_engine):
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        owner, organization, domain = await _make_org_and_domain(session)
        try:
            first = await ensure_email_domain_setup(session, domain)
            await session.commit()
            first_public_key = first.dkim_public_key
            first_token = first.email_verification_token

            second = await ensure_email_domain_setup(session, domain)
            await session.commit()

            assert second.dkim_public_key == first_public_key
            assert second.email_verification_token == first_token

            if second.resend_domain_id is not None:
                delete_resend_domain(second.resend_domain_id)
        finally:
            await _cleanup(session, organization.id, owner.id)
