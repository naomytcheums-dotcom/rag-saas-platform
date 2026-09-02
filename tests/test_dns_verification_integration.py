"""
Partie 1.4.1 -- real DNS resolution tests for
api/security/custom_domains.py's _lookup_txt_records/
check_domain_dns_txt_record. Unlike the Postgres/Redis/S3 integration
tests elsewhere in this suite, there's no service container this
project controls that can stand in for "a domain with a real TXT
record" -- so these tests hit the REAL public DNS system, but only ever
assert on outcomes that don't depend on any specific external party's
DNS content staying stable:

- a domain that doesn't exist -> NXDOMAIN handled as "no records", not
  an unhandled exception
- a long-lived, extremely stable domain -> SOME TXT records exist
  (proves real answer parsing/decoding works against a real response,
  without asserting on their exact content)
- a real domain that doesn't have OUR verification token -> False

Skips the whole module (not a failure) if outbound DNS isn't reachable
at all, same "skip if unreachable" convention as the Postgres/Celery/S3
integration tests.
"""

import uuid

import dns.asyncresolver
import dns.exception
import pytest

from api.security.custom_domains import _lookup_txt_records, check_domain_dns_txt_record


@pytest.fixture(scope="module", autouse=True)
async def _require_real_dns():
    try:
        resolver = dns.asyncresolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        await resolver.resolve("google.com", "A")
    except Exception as exc:
        pytest.skip(f"Outbound DNS is not reachable -- skipping real DNS verification tests ({exc})")


async def test_lookup_txt_records_handles_a_nonexistent_domain():
    records = await _lookup_txt_records(f"{uuid.uuid4().hex}.invalid")
    assert records == []


async def test_lookup_txt_records_parses_a_real_response():
    """google.com has carried TXT records (SPF and others) for many
    years -- this only asserts SOME records come back and are decoded
    as real strings, never their exact content, so it can't be broken
    by google.com changing its TXT records."""
    records = await _lookup_txt_records("google.com")
    assert len(records) > 0
    assert all(isinstance(record, str) for record in records)


async def test_check_domain_dns_txt_record_returns_false_when_the_token_is_not_present():
    """A real domain, a real DNS lookup, a token that will never be
    among its TXT records -- proves the real end-to-end path (not just
    the mocked one in tests/test_custom_domains.py) correctly reports
    "not verified" rather than raising."""
    matched = await check_domain_dns_txt_record("google.com", f"definitely-not-a-real-token-{uuid.uuid4().hex}")
    assert matched is False


async def test_check_domain_dns_txt_record_returns_false_for_a_nonexistent_domain():
    matched = await check_domain_dns_txt_record(f"{uuid.uuid4().hex}.invalid", "any-token")
    assert matched is False
