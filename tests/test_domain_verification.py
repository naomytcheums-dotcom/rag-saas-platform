"""
Partie 1.4.4 -- periodic domain-verification polling. Fast SQLite suite,
same tier as tests/test_custom_domains.py. The real DNS TXT lookup
(api/security/custom_domains.py's check_domain_dns_txt_record) is
monkeypatched throughout, same convention as that file -- no real
network call belongs here.

The real Celery tasks (api/tasks/domain_verification.py), which need a
real Postgres + running event-loop-free call shape, are tested for real
in tests/test_domain_verification_integration.py.
"""

import datetime as dt
import uuid

from sqlalchemy import select

from api.config import settings
from api.models.custom_domain import CustomDomain, CustomDomainStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.security.custom_domains import (
    apply_verification_check,
    check_all_pending_domains,
    poll_domain_verification,
    schedule_domain_verification,
)


async def _dns_matches(domain: str, token: str) -> bool:
    return True


async def _dns_does_not_match(domain: str, token: str) -> bool:
    return False


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    from api.models.user import User

    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def _add_member(db_session, org_id, user_id, role: OrganizationRole, invited_by=None):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


async def _add_domain(client, db_session, owner_token: str, org_id: str, domain: str) -> CustomDomain:
    await client.post(f"/organizations/{org_id}/domains", json={"domain": domain}, headers=_auth_header(owner_token))
    return await db_session.scalar(select(CustomDomain).where(CustomDomain.domain == domain))


# ------------------------------------------------------- poll_domain_verification --

async def test_poll_domain_verification_activates_when_dns_matches(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_matches)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_row = await _add_domain(client, db_session, owner_token, org["id"], "poll-match.acme.example")

    updated = await poll_domain_verification(db_session, "poll-match.acme.example")
    assert updated.status == CustomDomainStatus.active.value
    assert updated.verification_attempts == 1
    assert updated.last_verification_attempt_at is not None


async def test_poll_domain_verification_stays_pending_when_dns_does_not_match(client, db_session, register_payload, monkeypatch):
    """Vision critique Q2 -- an unreachable/non-propagated DNS record
    (indistinguishable from "not there yet" -- see
    check_domain_dns_txt_record's own docstring) leaves the domain
    `pending`, not `failed`, as long as neither limit is exhausted yet."""
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_does_not_match)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _add_domain(client, db_session, owner_token, org["id"], "poll-nomatch.acme.example")

    updated = await poll_domain_verification(db_session, "poll-nomatch.acme.example")
    assert updated.status == CustomDomainStatus.pending.value
    assert updated.verification_attempts == 1


async def test_poll_domain_verification_ignores_a_domain_that_is_no_longer_pending(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_matches)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _add_domain(client, db_session, owner_token, org["id"], "poll-active.acme.example")
    activated = await poll_domain_verification(db_session, "poll-active.acme.example")
    assert activated.status == CustomDomainStatus.active.value

    # A second poll on an already-active domain must be a complete no-op
    # -- in particular, it must NOT bump verification_attempts.
    unchanged = await poll_domain_verification(db_session, "poll-active.acme.example")
    assert unchanged.verification_attempts == 1


async def test_poll_domain_verification_raises_for_an_unregistered_domain(db_session):
    try:
        await poll_domain_verification(db_session, "never-registered.example")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "not a registered custom domain" in str(exc)


# --------------------------------------------------------- exhaustion limits --

async def test_domain_marked_failed_after_max_attempts(client, db_session, register_payload, monkeypatch):
    """Validation criterion: a domain becomes `failed` after too many
    attempts."""
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_does_not_match)
    monkeypatch.setattr(settings, "DOMAIN_VERIFICATION_MAX_ATTEMPTS", 2)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _add_domain(client, db_session, owner_token, org["id"], "exhaust-attempts.acme.example")

    first = await poll_domain_verification(db_session, "exhaust-attempts.acme.example")
    assert first.status == CustomDomainStatus.pending.value

    second = await poll_domain_verification(db_session, "exhaust-attempts.acme.example")
    assert second.status == CustomDomainStatus.failed.value
    assert second.verification_attempts == 2


async def test_domain_marked_failed_after_timeout_even_with_attempts_remaining(client, db_session, register_payload, monkeypatch):
    """The wall-clock timeout is a SEPARATE limit from the attempt count
    -- a domain past DOMAIN_VERIFICATION_TIMEOUT_MINUTES must fail even
    on its very first automatic attempt."""
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_does_not_match)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_row = await _add_domain(client, db_session, owner_token, org["id"], "exhaust-timeout.acme.example")

    domain_row.created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=settings.DOMAIN_VERIFICATION_TIMEOUT_MINUTES + 5)
    await db_session.commit()

    updated = await poll_domain_verification(db_session, "exhaust-timeout.acme.example")
    assert updated.status == CustomDomainStatus.failed.value
    assert updated.verification_attempts == 1  # failed on the FIRST attempt, well under max_attempts


async def test_apply_verification_check_does_not_fail_a_fresh_domain_on_first_mismatch(db_session, client, register_payload):
    """Sanity check on the two limits' defaults: a brand-new domain's
    first failed attempt must NOT immediately fail it."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_row = await _add_domain(client, db_session, owner_token, org["id"], "fresh-domain.acme.example")

    updated = await apply_verification_check(db_session, domain_row, dns_verified=False)
    assert updated.status == CustomDomainStatus.pending.value


# ------------------------------------------------------ check_all_pending_domains --

async def test_check_all_pending_domains_batches_correctly(client, db_session, register_payload, monkeypatch):
    """Validation criterion: the Celery task (here, its underlying
    batch function) checks pending domains -- activating matches,
    leaving still-unmatched-but-not-exhausted domains pending, and
    ignoring domains that are already active."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    async def _dns_by_domain(domain: str, token: str) -> bool:
        return domain == "batch-match.acme.example"

    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_by_domain)

    await _add_domain(client, db_session, owner_token, org["id"], "batch-match.acme.example")
    await _add_domain(client, db_session, owner_token, org["id"], "batch-nomatch.acme.example")

    # A third domain, already active, must be excluded entirely from the sweep.
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_matches)
    await _add_domain(client, db_session, owner_token, org["id"], "batch-already-active.acme.example")
    await poll_domain_verification(db_session, "batch-already-active.acme.example")
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_by_domain)

    results = await check_all_pending_domains(db_session)
    assert results == {"activated": 1, "failed": 0, "still_pending": 1}

    matched = await db_session.scalar(select(CustomDomain).where(CustomDomain.domain == "batch-match.acme.example"))
    unmatched = await db_session.scalar(select(CustomDomain).where(CustomDomain.domain == "batch-nomatch.acme.example"))
    already_active = await db_session.scalar(select(CustomDomain).where(CustomDomain.domain == "batch-already-active.acme.example"))
    assert matched.status == CustomDomainStatus.active.value
    assert unmatched.status == CustomDomainStatus.pending.value
    assert already_active.verification_attempts == 1  # untouched by THIS sweep


async def test_check_all_pending_domains_returns_zeroed_counts_when_nothing_pending(db_session):
    results = await check_all_pending_domains(db_session)
    assert results == {"activated": 0, "failed": 0, "still_pending": 0}


# ------------------------------------------------------- schedule_domain_verification --

async def test_schedule_domain_verification_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    """Vision critique Q2 -- a broker hiccup while scheduling the
    post-creation head-start check must never surface as an error to
    whatever called it (add_custom_domain)."""

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.domain_verification.poll_one_domain.apply_async", _boom)
    schedule_domain_verification("does-not-matter.example")  # must not raise


async def test_adding_a_domain_schedules_a_follow_up_check(client, db_session, register_payload, monkeypatch):
    scheduled = []
    monkeypatch.setattr("api.security.custom_domains.schedule_domain_verification", lambda domain: scheduled.append(domain))

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/domains", json={"domain": "schedules-me.acme.example"}, headers=_auth_header(owner_token))

    assert scheduled == ["schedules-me.acme.example"]


# ------------------------------------------------------------- manual verify endpoint --

async def test_owner_can_manually_verify_a_domain(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_matches)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "manual-verify.acme.example"}, headers=_auth_header(owner_token))
    domain_id = created.json()["id"]

    response = await client.post(f"/organizations/{org['id']}/domains/{domain_id}/verify", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["status"] == CustomDomainStatus.active.value


async def test_manual_verification_does_not_increment_the_attempt_counter(client, db_session, register_payload, monkeypatch):
    """Design decision: a human clicking "verify now" is NOT subject to
    DOMAIN_VERIFICATION_MAX_ATTEMPTS -- that limit exists to bound
    AUTOMATIC background retrying only."""
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_does_not_match)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "manual-noattempt.acme.example"}, headers=_auth_header(owner_token))
    domain_id = created.json()["id"]

    response = await client.post(f"/organizations/{org['id']}/domains/{domain_id}/verify", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["status"] == CustomDomainStatus.failed.value
    assert response.json()["verification_attempts"] == 0


async def test_admin_cannot_manually_verify_a_domain(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "manual-admin.acme.example"}, headers=_auth_header(owner_token))
    domain_id = created.json()["id"]

    admin_token, admin = await _register(client, db_session, "domainverifyadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.post(f"/organizations/{org['id']}/domains/{domain_id}/verify", headers=_auth_header(admin_token))
    assert response.status_code == 403


async def test_manual_verification_for_a_domain_in_another_org_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "manual-crossorg.acme.example"}, headers=_auth_header(owner_token))
    domain_id = created.json()["id"]

    other_owner_token, other_owner = await _register(client, db_session, "manualcrossorgother@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")

    response = await client.post(f"/organizations/{other_org['id']}/domains/{domain_id}/verify", headers=_auth_header(other_owner_token))
    assert response.status_code == 404


# --------------------------------------------------------------- status endpoint --

async def test_owner_can_get_domain_status(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_does_not_match)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "status-check.acme.example"}, headers=_auth_header(owner_token))
    domain_id = created.json()["id"]

    await poll_domain_verification(db_session, "status-check.acme.example")

    response = await client.get(f"/organizations/{org['id']}/domains/{domain_id}/status", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == CustomDomainStatus.pending.value
    assert body["verification_attempts"] == 1
    assert body["max_attempts"] == settings.DOMAIN_VERIFICATION_MAX_ATTEMPTS
    assert body["last_verification_attempt_at"] is not None
    assert body["timeout_at"] > body["created_at"]


async def test_admin_cannot_get_domain_status(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "status-admin.acme.example"}, headers=_auth_header(owner_token))
    domain_id = created.json()["id"]

    admin_token, admin = await _register(client, db_session, "statusadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/domains/{domain_id}/status", headers=_auth_header(admin_token))
    assert response.status_code == 403


async def test_status_for_a_domain_in_another_org_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "status-crossorg.acme.example"}, headers=_auth_header(owner_token))
    domain_id = created.json()["id"]

    other_owner_token, other_owner = await _register(client, db_session, "statuscrossorgother@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")

    response = await client.get(f"/organizations/{other_org['id']}/domains/{domain_id}/status", headers=_auth_header(other_owner_token))
    assert response.status_code == 404
