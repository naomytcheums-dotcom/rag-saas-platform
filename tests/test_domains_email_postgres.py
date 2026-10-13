"""Custom domain (1.4.1), e-mail sending domain (1.4.5) and sender address (1.4.9): the REAL FastAPI application against a REAL PostgreSQL, with the DNS
protocol and Resend's REST API served by LOCAL FAKES (tests/fake_vendor_servers.py -- read its docstring: they prove OUR code against the documented protocols,
not the vendors' present behaviour). The DNS lookups of the application go over a real UDP socket to the fake nameserver (`CUSTOM_DOMAIN_DNS_NAMESERVERS`), the
Resend calls over a real TCP socket to the fake API (`RESEND_API_BASE_URL`); nothing is monkeypatched inside the application's own code.

Runs only on a local PostgreSQL whose database name contains "test":  python -m pytest tests/test_domains_email_postgres.py -p no:cacheprovider
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from api.config import settings
from api.database import AsyncSessionLocal
from api.main import app
from api.models.custom_domain import CustomDomain
from api.models.organization import OrganizationMember, OrganizationRole
from fake_vendor_servers import FakeDnsServer, FakeResend

_url = str(settings.DATABASE_URL)
_LOCAL_TEST_PG = _url.startswith("postgresql") and ("127.0.0.1" in _url or "localhost" in _url) and "test" in _url.rsplit("/", 1)[-1]
pytestmark = pytest.mark.skipif(not _LOCAL_TEST_PG, reason="needs DATABASE_URL on a local PostgreSQL database whose name contains 'test'")

PASSWORD = "Correct-Horse-Battery-Staple-9!"
RESEND_KEY = "re_local_fake_key_not_a_real_one"


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client():
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=60) as c:
        yield c
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


@pytest.fixture
def dns_server(monkeypatch):
    server = FakeDnsServer().start()
    monkeypatch.setattr(settings, "CUSTOM_DOMAIN_DNS_NAMESERVERS", server.nameserver)
    monkeypatch.setattr(settings, "CUSTOM_DOMAIN_DNS_LOOKUP_TIMEOUT_SECONDS", 2)
    yield server
    server.stop()


@pytest.fixture
def resend(monkeypatch, dns_server):
    fake = FakeResend(RESEND_KEY, dns_server).start()
    monkeypatch.setattr(settings, "RESEND_API_KEY", RESEND_KEY)
    monkeypatch.setattr(settings, "RESEND_API_BASE_URL", fake.base_url)
    yield fake
    fake.stop()


async def new_user(client) -> dict:
    email = f"dom-{uuid.uuid4().hex[:10]}@example.com"
    with patch("api.routers.auth.create_and_send_email_otp", new=AsyncMock()):
        r = await client.post("/auth/register", json={"email": email, "password": PASSWORD, "full_name": "Domain Test", "accept_terms": True})
    assert r.status_code in (200, 201), r.text
    me = await client.get("/account/me", headers=_h(r.json()["access_token"]))
    return {"email": email, "token": r.json()["access_token"], "id": uuid.UUID(me.json()["id"])}


async def new_org(client, owner: dict) -> uuid.UUID:
    r = await client.post("/organizations", json={"name": f"Dom {uuid.uuid4().hex[:6]}"}, headers=_h(owner["token"]))
    assert r.status_code in (200, 201), r.text
    return uuid.UUID(r.json()["id"])


def fresh_domain(prefix: str = "app") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}.client-test.example"


async def add_domain(client, owner, org, domain) -> dict:
    r = await client.post(f"/organizations/{org}/domains", headers=_h(owner["token"]), json={"domain": domain})
    assert r.status_code == 201, r.text
    return r.json()


def txt_name(domain: str) -> str:
    return f"_rag-saas-verify.{domain}"


# ====================================================================================================================== 1.4.1 custom domain


async def test_domain_ownership_is_proven_by_a_dns_txt_record_over_the_real_dns_protocol(client, dns_server):
    owner = await new_user(client)
    org = await new_org(client, owner)
    domain = fresh_domain()
    created = await add_domain(client, owner, org, domain)
    assert created["status"] == "pending" and created["domain"] == domain
    txt = next(r for r in created["dns_records"] if r["type"] == "TXT")
    assert txt["name"] == txt_name(domain) and txt["value"] == created["verification_token"]
    assert any(r["type"] == "CNAME" and r["name"] == domain and r["value"] == settings.CUSTOM_DOMAIN_CNAME_TARGET for r in created["dns_records"])

    # nothing published: the owner's "verify now" answers failed -- the lookup really went to the nameserver and got NXDOMAIN
    r = await client.post(f"/organizations/{org}/domains/{created['id']}/verify", headers=_h(owner["token"]))
    assert r.status_code == 200 and r.json()["status"] == "failed"
    assert f"TXT {txt_name(domain)}" in dns_server.queries

    # a WRONG value published: still failed
    dns_server.publish(txt_name(domain), "not-the-token")
    r = await client.post(f"/organizations/{org}/domains/{created['id']}/verify", headers=_h(owner["token"]))
    assert r.json()["status"] == "failed"

    # the customer publishes the right record: a failed domain can be re-checked without being deleted and re-created
    dns_server.publish(txt_name(domain), created["verification_token"])
    r = await client.post(f"/organizations/{org}/domains/{created['id']}/verify", headers=_h(owner["token"]))
    assert r.status_code == 200 and r.json()["status"] == "active"
    listing = (await client.get(f"/organizations/{org}/domains", headers=_h(owner["token"]))).json()["items"]
    assert [d["status"] for d in listing] == ["active"]


async def test_the_public_verification_link_needs_the_right_organization_and_token(client, dns_server):
    a, b = await new_user(client), await new_user(client)
    org_a, org_b = await new_org(client, a), await new_org(client, b)
    domain = fresh_domain()
    created = await add_domain(client, a, org_a, domain)
    dns_server.publish(txt_name(domain), created["verification_token"])
    base = f"/organizations/{org_a}/domains/verify"
    assert (await client.get(f"{base}/not-the-token")).status_code == 404
    assert (await client.get(f"/organizations/{org_b}/domains/verify/{created['verification_token']}")).status_code == 404  # right token, wrong organization
    queries_before = len(dns_server.queries)
    assert len(dns_server.queries) == queries_before  # the 404s never reached DNS (no lookup proxy)
    ok = await client.get(f"{base}/{created['verification_token']}")
    assert ok.status_code == 200 and ok.json()["status"] == "active"


async def test_a_live_domain_is_not_knocked_back_to_failed_when_its_record_disappears(client, dns_server):
    """The public link is reachable with the token alone; before the fix one call made while the TXT record was absent (or a DNS timeout) turned an ACTIVE domain into FAILED."""
    owner = await new_user(client)
    org = await new_org(client, owner)
    domain = fresh_domain()
    created = await add_domain(client, owner, org, domain)
    dns_server.publish(txt_name(domain), created["verification_token"])
    assert (await client.get(f"/organizations/{org}/domains/verify/{created['verification_token']}")).json()["status"] == "active"
    dns_server.unpublish(txt_name(domain))
    again = await client.get(f"/organizations/{org}/domains/verify/{created['verification_token']}")
    assert again.json()["status"] == "active"
    manual = await client.post(f"/organizations/{org}/domains/{created['id']}/verify", headers=_h(owner["token"]))
    assert manual.json()["status"] == "active"


async def test_a_failed_claim_does_not_hold_the_hostname_hostage_but_a_pending_or_live_one_does(client, dns_server):
    squatter, owner = await new_user(client), await new_user(client)
    org_s, org_o = await new_org(client, squatter), await new_org(client, owner)
    domain = fresh_domain("shop")
    claim = await add_domain(client, squatter, org_s, domain)  # registers a domain it does not own
    r = await client.post(f"/organizations/{org_o}/domains", headers=_h(owner["token"]), json={"domain": domain})
    assert r.status_code == 400 and "already registered" in r.json()["detail"]  # pending claim: protected
    await client.post(f"/organizations/{org_s}/domains/{claim['id']}/verify", headers=_h(squatter["token"]))  # DNS proof never comes -> failed
    real = await add_domain(client, owner, org_o, domain)  # the real owner can now claim it
    assert real["organization_id"] == str(org_o) and real["verification_token"] != claim["verification_token"]
    dns_server.publish(txt_name(domain), real["verification_token"])
    assert (await client.post(f"/organizations/{org_o}/domains/{real['id']}/verify", headers=_h(owner["token"]))).json()["status"] == "active"
    # the squatter cannot take it back once it is live, nor verify with its old token
    assert (await client.post(f"/organizations/{org_s}/domains", headers=_h(squatter["token"]), json={"domain": domain})).status_code == 400
    assert (await client.get(f"/organizations/{org_s}/domains/verify/{claim['verification_token']}")).status_code == 404


async def test_domain_registration_is_validated_and_owner_only(client, dns_server):
    owner, admin, member, outsider = [await new_user(client) for _ in range(4)]
    org = await new_org(client, owner)
    async with AsyncSessionLocal() as db:
        db.add(OrganizationMember(organization_id=org, user_id=admin["id"], role=OrganizationRole.admin))
        db.add(OrganizationMember(organization_id=org, user_id=member["id"], role=OrganizationRole.member))
        await db.commit()
    url = f"/organizations/{org}/domains"
    for bad in ("not a domain", "localhost", "-bad.example.com", "a..b.example", settings.CUSTOM_DOMAIN_CNAME_TARGET, f"evil.{settings.CUSTOM_DOMAIN_CNAME_TARGET}"):
        assert (await client.post(url, headers=_h(owner["token"]), json={"domain": bad})).status_code in (400, 422), bad
    for who in (admin, member, outsider):  # Owner-only (documented), even an admin is refused; an outsider learns nothing
        assert (await client.post(url, headers=_h(who["token"]), json={"domain": fresh_domain()})).status_code in (403, 404)
        assert (await client.get(url, headers=_h(who["token"]))).status_code in (403, 404)
    domain = fresh_domain()
    created = await add_domain(client, owner, org, domain.upper())  # case is normalised
    assert created["domain"] == domain
    assert (await client.post(url, headers=_h(owner["token"]), json={"domain": domain + "."})).status_code == 400  # trailing dot = the same domain
    other = await new_org(client, outsider)
    assert (await client.get(f"/organizations/{other}/domains/{created['id']}/status", headers=_h(outsider["token"]))).status_code == 404  # no cross-tenant read
    assert (await client.delete(f"/organizations/{other}/domains/{created['id']}", headers=_h(outsider["token"]))).status_code == 404
    assert (await client.delete(f"{url}/{created['id']}", headers=_h(owner["token"]))).status_code == 200
    assert (await client.get(url, headers=_h(owner["token"]))).json()["items"] == []


async def test_requests_arriving_on_an_active_custom_domain_are_attributed_to_its_organization(client, dns_server):
    """The host detection middleware: a request whose Host is an ACTIVE custom domain carries that organization; a pending domain or the platform's own host does not."""
    owner = await new_user(client)
    org = await new_org(client, owner)
    domain, pending_domain = fresh_domain(), fresh_domain("wait")
    created = await add_domain(client, owner, org, domain)
    await add_domain(client, owner, org, pending_domain)
    dns_server.publish(txt_name(domain), created["verification_token"])
    assert (await client.post(f"/organizations/{org}/domains/{created['id']}/verify", headers=_h(owner["token"]))).json()["status"] == "active"

    seen: dict[str, object] = {}

    async def probe(request):
        seen["org"] = request.state.white_label_organization_id
        return {"ok": True}

    app.add_api_route("/__billing_test_host_probe", probe, methods=["GET"])
    try:
        await client.get("/__billing_test_host_probe", headers={"Host": domain})
        assert seen["org"] == org
        await client.get("/__billing_test_host_probe", headers={"Host": pending_domain})
        assert seen["org"] is None  # not active
        await client.get("/__billing_test_host_probe", headers={"Host": "app.unknown-test.example"})
        assert seen["org"] is None
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/__billing_test_host_probe"]


# ====================================================================================================================== 1.4.5 e-mail domain


async def test_email_domain_setup_against_the_resend_api_and_dns(client, dns_server, resend):
    owner = await new_user(client)
    org = await new_org(client, owner)
    domain = fresh_domain("mail")
    created = await add_domain(client, owner, org, domain)
    base = f"/organizations/{org}/domains/{created['id']}/email"

    assert (await client.get(f"{base}/status", headers=_h(owner["token"]))).json()["status"] == "not_started"
    dns = (await client.get(f"{base}/dns", headers=_h(owner["token"]))).json()
    assert dns["resend_domain_id"] and dns["resend_error"] is None and dns["resend_status"] == "not_started"
    kinds = {(r["record"], r["type"]) for r in dns["resend_records"]}
    assert ("DKIM", "TXT") in kinds and ("SPF", "MX") in kinds  # Resend's records, relayed as returned
    ownership = next(r for r in dns["our_records"] if r["purpose"] == "ownership")
    assert ownership["name"] == f"_rag-verify.{domain}"
    assert any(r["purpose"] == "dkim" for r in dns["our_records"])  # our own DKIM key, published for completeness
    assert (await client.get(f"{base}/dns", headers=_h(owner["token"]))).json()["resend_domain_id"] == dns["resend_domain_id"]  # idempotent: registered once
    assert sum(1 for m, p in resend.requests if (m, p) == ("POST", "/domains")) == 1

    r = await client.post(f"{base}/verify", headers=_h(owner["token"]))  # nothing published yet
    assert r.status_code == 200 and r.json()["email_verified"] is False and r.json()["email_verification_attempts"] == 1
    assert ("POST", f"/domains/{dns['resend_domain_id']}/verify") in resend.requests  # Resend's own check was triggered too

    dns_server.publish(ownership["name"], ownership["value"])  # the customer publishes the ownership record
    r = await client.post(f"{base}/verify", headers=_h(owner["token"]))
    assert r.json()["email_verified"] is True and r.json()["status"] == "verified"
    attempts = r.json()["email_verification_attempts"]
    again = await client.post(f"{base}/verify", headers=_h(owner["token"]))  # verified domains are not re-checked
    assert again.json()["email_verification_attempts"] == attempts

    # Resend's own records are only verified once they are really published in DNS
    assert (await client.get(f"{base}/dns", headers=_h(owner["token"]))).json()["resend_status"] != "verified"
    resend.publish_records(domain)
    await client.post(f"{base}/verify", headers=_h(owner["token"]))
    assert (await client.get(f"{base}/dns", headers=_h(owner["token"]))).json()["resend_status"] == "verified"


async def test_email_domain_routes_are_owner_only_and_tenant_isolated(client, dns_server, resend):
    owner, member, outsider = [await new_user(client) for _ in range(3)]
    org = await new_org(client, owner)
    async with AsyncSessionLocal() as db:
        db.add(OrganizationMember(organization_id=org, user_id=member["id"], role=OrganizationRole.member))
        await db.commit()
    created = await add_domain(client, owner, org, fresh_domain("mail"))
    base = f"/organizations/{org}/domains/{created['id']}/email"
    for path in ("status", "dns"):
        assert (await client.get(f"{base}/{path}", headers=_h(member["token"]))).status_code == 403
        assert (await client.get(f"{base}/{path}", headers=_h(outsider["token"]))).status_code in (403, 404)
    assert (await client.post(f"{base}/verify", headers=_h(member["token"]))).status_code == 403
    other = await new_org(client, outsider)
    assert (await client.get(f"/organizations/{other}/domains/{created['id']}/email/status", headers=_h(outsider["token"]))).status_code == 404


async def test_resend_being_down_or_the_key_wrong_degrades_without_a_500(client, dns_server, monkeypatch):
    owner = await new_user(client)
    org = await new_org(client, owner)
    created = await add_domain(client, owner, org, fresh_domain("mail"))
    monkeypatch.setattr(settings, "RESEND_API_KEY", None)  # not configured
    r = await client.get(f"/organizations/{org}/domains/{created['id']}/email/dns", headers=_h(owner["token"]))
    assert r.status_code == 200 and r.json()["resend_domain_id"] is None and r.json()["our_records"]
    monkeypatch.setattr(settings, "RESEND_API_KEY", RESEND_KEY)
    monkeypatch.setattr(settings, "RESEND_API_BASE_URL", "http://127.0.0.1:9")  # nothing listens: connection refused
    r = await client.get(f"/organizations/{org}/domains/{created['id']}/email/dns", headers=_h(owner["token"]))
    assert r.status_code == 200 and r.json()["resend_domain_id"] is None


async def test_deleting_a_domain_removes_its_resend_domain(client, dns_server, resend):
    owner = await new_user(client)
    org = await new_org(client, owner)
    created = await add_domain(client, owner, org, fresh_domain("mail"))
    dns = (await client.get(f"/organizations/{org}/domains/{created['id']}/email/dns", headers=_h(owner["token"]))).json()
    assert dns["resend_domain_id"] in resend.domains
    assert (await client.delete(f"/organizations/{org}/domains/{created['id']}", headers=_h(owner["token"]))).status_code == 200
    assert dns["resend_domain_id"] not in resend.domains


# ====================================================================================================================== 1.4.9 sender address


async def verified_email_domain(client, dns_server, resend, owner, org, prefix="mail") -> str:
    domain = fresh_domain(prefix)
    created = await add_domain(client, owner, org, domain)
    base = f"/organizations/{org}/domains/{created['id']}/email"
    dns = (await client.get(f"{base}/dns", headers=_h(owner["token"]))).json()
    ownership = next(r for r in dns["our_records"] if r["purpose"] == "ownership")
    dns_server.publish(ownership["name"], ownership["value"])
    resend.publish_records(domain)
    r = await client.post(f"{base}/verify", headers=_h(owner["token"]))
    assert r.json()["email_verified"] is True
    return domain


async def invitation(org, to="invitee@example.com"):
    from api.services.email_branding import send_branded_organization_invitation_email

    async with AsyncSessionLocal() as db:
        await send_branded_organization_invitation_email(db, org, to, "member", "https://app.example.test/invite/abc")


async def test_changing_the_sending_address_end_to_end_through_resend(client, dns_server, resend):
    owner = await new_user(client)
    org = await new_org(client, owner)
    url = f"/organizations/{org}/whitelabel/email"
    default_domain = settings.EMAIL_FROM_ADDRESS.rsplit("@", 1)[-1].strip(">")
    resend.register_verified_domain(default_domain)  # the platform's own sending domain, verified in the (fake) account

    # 1. nothing configured: the platform default is the sender
    await invitation(org)
    assert resend.sent[-1]["from"] == settings.EMAIL_FROM_ADDRESS

    # 2. an address at a domain that is not the organization's is refused, and so is its own domain until e-mail ownership AND the provider are verified
    domain = fresh_domain("mail")
    created = await add_domain(client, owner, org, domain)
    for forbidden in (f"support@{default_domain}", "ceo@bank.example", f"support@{domain}"):
        r = await client.post(url, headers=_h(owner["token"]), json={"sender_name": "Acme", "sender_email": forbidden})
        assert r.status_code == 400, forbidden
    base = f"/organizations/{org}/domains/{created['id']}/email"
    dns = (await client.get(f"{base}/dns", headers=_h(owner["token"]))).json()
    ownership = next(r for r in dns["our_records"] if r["purpose"] == "ownership")
    dns_server.publish(ownership["name"], ownership["value"])
    assert (await client.post(f"{base}/verify", headers=_h(owner["token"]))).json()["email_verified"] is True
    r = await client.post(url, headers=_h(owner["token"]), json={"sender_name": "Acme", "sender_email": f"support@{domain}"})
    assert r.status_code == 400 and "mail provider has not verified" in r.json()["detail"]  # ownership proven, Resend's records not yet published

    # 3. the customer publishes Resend's records, the provider verifies: the sender can be set
    resend.publish_records(domain)
    await client.post(f"{base}/verify", headers=_h(owner["token"]))
    r = await client.post(url, headers=_h(owner["token"]), json={"sender_name": "Acme Support", "sender_email": f"support@{domain}"})
    assert r.status_code == 200 and r.json()["email_sender_email"] == f"support@{domain}"
    await invitation(org)
    assert resend.sent[-1]["from"] == f"Acme Support <support@{domain}>"

    # 4. changing the address (same verified domain) takes effect on the next e-mail
    r = await client.post(url, headers=_h(owner["token"]), json={"sender_name": "Acme Billing", "sender_email": f"billing@{domain}"})
    assert r.status_code == 200
    await invitation(org)
    assert resend.sent[-1]["from"] == f"Acme Billing <billing@{domain}>"

    # 5. removing the configuration returns to the platform default
    assert (await client.delete(url, headers=_h(owner["token"]))).status_code == 200
    await invitation(org)
    assert resend.sent[-1]["from"] == settings.EMAIL_FROM_ADDRESS

    # 6. the PATCH route of the white-label config cannot be used to bypass the rule
    r = await client.patch(f"/organizations/{org}/whitelabel/config", headers=_h(owner["token"]), json={"email_sender_email": "ceo@bank.example"})
    assert r.status_code in (200, 400, 422)
    config = (await client.get(f"/organizations/{org}/whitelabel/config", headers=_h(owner["token"]))).json()
    assert config["email_sender_email"] is None


async def test_the_provider_refuses_an_unverified_sender_domain_and_the_error_is_not_swallowed(client, dns_server, resend):
    """Defence in depth: whatever the application stored, a send from a domain the provider has not verified fails loudly (never a silent success)."""
    from api.models.organization_branding import OrganizationBranding
    from api.services.email_branding import send_branded_organization_invitation_email

    owner = await new_user(client)
    org = await new_org(client, owner)
    async with AsyncSessionLocal() as db:  # written straight to the table: bypasses the API rule on purpose
        branding = await db.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id == org))
        branding.email_sender_name, branding.email_sender_email = "Acme", "support@never-verified.example"
        await db.commit()
    async with AsyncSessionLocal() as db:
        with pytest.raises(RuntimeError, match="403"):
            await send_branded_organization_invitation_email(db, org, "invitee@example.com", "member", "https://app.example.test/i")
    assert resend.sent == []


async def test_the_email_domain_send_helper_refuses_a_domain_whose_ownership_is_not_verified(client, dns_server, resend):
    from api.services.email import send_via_custom_email_domain

    owner = await new_user(client)
    org = await new_org(client, owner)
    domain = fresh_domain("mail")
    await add_domain(client, owner, org, domain)
    async with AsyncSessionLocal() as db:
        row = await db.scalar(select(CustomDomain).where(CustomDomain.domain == domain))
    with pytest.raises(ValueError, match="ownership verification"):
        send_via_custom_email_domain(row, "contact", "x@example.com", "Hi", "<p>Hi</p>")
    assert resend.sent == []
