"""
Partie 1.4.3 -- REAL ACME protocol tests against Let's Encrypt's
STAGING server (never production -- see api/config.py's
ACME_DIRECTORY_URL). No service container can stand in for "a real
ACME server" the way Postgres/Redis/MinIO do for other integrations,
so these tests hit the actual public staging endpoint -- but only ever
assert on outcomes that don't require owning a real domain:

- real account registration (idempotent, no domain involved at all)
- opening a real order for a syntactically-valid-but-unowned domain --
  Let's Encrypt accepts the ORDER without checking ownership yet, only
  the eventual challenge-completion needs real control
- the real DNS-01 challenge Let's Encrypt computes matches this
  module's own understanding of the record name/value
- resuming an order WITHOUT ever publishing the real DNS record
  correctly reports failure/pending, never a false success

Skips the whole module (not a failure) if the staging server isn't
reachable, same "skip if unreachable" convention as the Postgres/
Celery/S3/DNS integration tests elsewhere in this suite.
"""

import uuid

import pytest
import requests
from acme import challenges, errors

from api.security.ssl_certificates import _build_csr_pem, _generate_key, _open_order, _register_account, _resume_order

_TEST_CONTACT_EMAIL = "acme-integration-tests@rag-saas-platform-testing.dev"
# A syntactically valid public-suffix domain Let's Encrypt will accept
# an ORDER for -- but nobody controls its DNS, so no challenge on it
# can ever actually validate. A fresh random subdomain per test run so
# concurrent CI runs never collide on the same order.
_TEST_DOMAIN_BASE = "rag-saas-platform-nonexistent-domain.com"


@pytest.fixture(scope="module", autouse=True)
def _require_staging_reachable():
    from api.config import settings
    try:
        response = requests.get(settings.ACME_DIRECTORY_URL, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        pytest.skip(f"Let's Encrypt staging is not reachable -- skipping real ACME integration tests ({exc})")


def _test_domain() -> str:
    return f"itest-{uuid.uuid4().hex[:12]}.{_TEST_DOMAIN_BASE}"


def test_account_registration_is_real_and_idempotent():
    """
    A real `new_account` call against Let's Encrypt staging. RFC 8555
    account creation is idempotent per key -- registering the SAME key
    twice resolves to the SAME account, not a new one -- but this
    library surfaces that as `errors.ConflictError(location)` rather
    than transparently returning the existing resource (confirmed here
    against the real server, not assumed from the RFC text alone).
    api/security/ssl_certificates.py's get_or_create_acme_account never
    hits this path in practice -- it checks its own database first and
    only ever calls _register_account once per directory -- but this
    pins down the real library behavior so that design is verified
    correct, not just assumed.
    """
    account_key, account_url = _register_account(_TEST_CONTACT_EMAIL)
    assert account_url.startswith("https://acme-staging-v02.api.letsencrypt.org/")

    from acme import messages
    from api.security.ssl_certificates import _client_for

    acme_client = _client_for(account_key, account_url=None)
    try:
        acme_client.new_account(messages.NewRegistration.from_data(email=_TEST_CONTACT_EMAIL, terms_of_service_agreed=True))
        assert False, "expected a ConflictError for an already-registered key"
    except errors.ConflictError as exc:
        assert exc.location == account_url


def test_opening_a_real_order_computes_a_well_formed_dns01_challenge():
    """Real order creation for a syntactically-valid, unowned domain --
    Let's Encrypt accepts it (ownership is only checked at challenge
    time, not order-creation time). Confirms the computed DNS-01
    record name/value are real, well-formed ACME values, not
    fabricated."""
    account_key, account_url = _register_account(_TEST_CONTACT_EMAIL)
    domain = _test_domain()
    cert_key = _generate_key()

    order_url, challenge_url, record_name, record_value, finalize_url = _open_order(account_key, account_url, domain, cert_key)

    assert order_url.startswith("https://acme-staging-v02.api.letsencrypt.org/")
    assert challenge_url.startswith("https://acme-staging-v02.api.letsencrypt.org/")
    assert record_name == f"_acme-challenge.{domain}"
    # A real ACME DNS-01 validation value: base64url(sha256(...)), no
    # padding -- 43 characters for a 32-byte SHA-256 digest.
    assert len(record_value) == 43
    assert all(c.isalnum() or c in "-_" for c in record_value)
    assert finalize_url.startswith("https://acme-staging-v02.api.letsencrypt.org/")


def test_resuming_an_order_without_publishing_dns_reports_failure():
    """The exact scenario this deployment always faces (see
    api/models/ssl_certificate.py's own docstring: no DNS-write access
    exists) -- answering the challenge without ever publishing the real
    TXT record must be reported as `failed`, never a false `issued`."""
    account_key, account_url = _register_account(_TEST_CONTACT_EMAIL)
    domain = _test_domain()
    cert_key = _generate_key()

    order_url, challenge_url, _record_name, _record_value, _finalize_url = _open_order(account_key, account_url, domain, cert_key)

    result = _resume_order(account_key, account_url, order_url, challenge_url, cert_key, domain)

    assert result["outcome"] == "failed"
    assert "DNS" in result["detail"] or "dns" in result["detail"].lower()


def test_resuming_an_order_before_answering_reports_pending():
    """Real behavior check: an order that has never been answered at
    all (this module's own _open_order deliberately never calls
    answer_challenge -- see its docstring) is still `pending` on Let's
    Encrypt's side. _resume_order answers it once and then polls --
    since nothing was published, the same "failed" outcome as above is
    the correct, honest result; this test exists to pin down that an
    UNANSWERED authorization really does start life as STATUS_PENDING
    on the real server, confirming _resume_order's own pending-check
    branch is reachable in practice, not just in mocked tests."""
    account_key, account_url = _register_account(_TEST_CONTACT_EMAIL)
    domain = _test_domain()
    cert_key = _generate_key()

    order_url, _challenge_url, _record_name, _record_value, _finalize_url = _open_order(account_key, account_url, domain, cert_key)

    from api.security.ssl_certificates import _client_for
    from acme import messages
    acme_client = _client_for(account_key, account_url)
    order_body = messages.Order.from_json(acme_client.net.get(order_url).json())
    authz_body = messages.Authorization.from_json(acme_client.net.get(order_body.authorizations[0]).json())
    assert authz_body.status == messages.STATUS_PENDING
    dns01_challenge = next(c for c in authz_body.challenges if isinstance(c.chall, challenges.DNS01))
    assert dns01_challenge.status == messages.STATUS_PENDING
