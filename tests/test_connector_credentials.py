"""Importers and CRM connectors use the credentials of the organization that calls them, never the server's (docs/DECISIONS.md D17).

What was wrong: every connector read ONE token from the server settings; any member with `documents:write` could import from the operator's account, and no customer could
connect their own. What is proved here:

  * default: an organization with no credentials is refused (403) even when the server has a token;
  * an organization's own credentials are the ones sent to the service (URL, e-mail, token), the server's are never used while its scope is active;
  * two organizations never see each other's credentials;
  * the secrets are encrypted at rest and never returned by the API;
  * who may read / write them; the address fields are validated (https, public address, vendor domain, strict formats);
  * the legacy shared mode still works when the operator switches it on explicitly;
  * the scope is reset after the request, and background tasks resolve it from the database (PostgreSQL part at the end, opt-in by environment)."""

import json
import uuid

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.connector_credential import ConnectorCredential
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.encryption import generate_encryption_key
from api.services import connector_credentials as cc
from api.services.connector_credentials import connector_settings

SERVER_TOKEN = "SERVER-WIDE-JIRA-TOKEN-must-never-leak"


@pytest.fixture(autouse=True)
def _per_organization_mode(monkeypatch):
    """Overrides the suite-wide legacy default of tests/conftest.py: this file tests the production default."""
    monkeypatch.setattr(settings, "CONNECTORS_ALLOW_PLATFORM_CREDENTIALS", False)
    monkeypatch.setattr(settings, "ENCRYPTION_MASTER_KEY", generate_encryption_key())
    monkeypatch.setattr(settings, "JIRA_ENABLED", True)
    monkeypatch.setattr(settings, "JIRA_BASE_URL", "https://server-wide.atlassian.net")
    monkeypatch.setattr(settings, "JIRA_EMAIL", "operator@example.com")
    monkeypatch.setattr(settings, "JIRA_API_TOKEN", SERVER_TOKEN)
    monkeypatch.setattr(cc, "_public_host_or_raise", lambda host: None)  # no DNS in these tests; the address rules have their own tests below


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _owner_and_org(client, db_session, email):
    token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    org = (await client.post("/organizations", json={"name": f"Conn {uuid.uuid4().hex[:6]}"}, headers=_auth(token))).json()
    return token, org


def _jira(email="ada@acme.example", token="ACME-OWN-TOKEN", base="https://acme.atlassian.net"):
    return {"JIRA_BASE_URL": base, "JIRA_EMAIL": email, "JIRA_API_TOKEN": token}


@pytest.fixture
def captured(monkeypatch):
    """Replaces the HTTP client used by the Jira importer with a recorder that answers like Jira."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"url": str(request.url), "authorization": request.headers.get("authorization", "")})
        return httpx.Response(200, json={"issues": [{"id": "1", "key": "ACME-1", "fields": {"summary": "Broken login"}}]})

    real = httpx.AsyncClient
    monkeypatch.setattr("api.services.jira_extraction.httpx.AsyncClient", lambda *a, **k: real(transport=httpx.MockTransport(handler), timeout=5))

    async def fake_ingest(db, org_id, user_id, source, records):
        return len(records)

    monkeypatch.setattr("api.routers.crm._ingest_records_as_documents", fake_ingest)
    return seen


def _basic(email, token):
    import base64

    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()


# ---------------------------------------------------------------- default: refused


async def test_an_organization_without_credentials_is_refused_even_when_the_server_has_a_token(client, db_session, register_payload, captured):
    token, org = await _owner_and_org(client, db_session, register_payload["email"])
    response = await client.post(f"/organizations/{org['id']}/crm/jira/import", json={"limit": 5}, headers=_auth(token))
    assert response.status_code == 403, response.text
    assert "has not connected jira" in response.text
    assert captured == [], "the server's token was used"


# ---------------------------------------------------------------- own credentials used


async def test_the_organization_own_credentials_are_sent_and_the_server_ones_never_are(client, db_session, register_payload, captured):
    token, org = await _owner_and_org(client, db_session, register_payload["email"])
    assert (await client.put(f"/organizations/{org['id']}/connectors/jira", json={"fields": _jira()}, headers=_auth(token))).status_code == 200

    response = await client.post(f"/organizations/{org['id']}/crm/jira/import", json={"limit": 5}, headers=_auth(token))

    assert response.status_code == 200, response.text
    assert response.json()["imported"] == 1
    assert len(captured) == 1
    assert captured[0]["url"].startswith("https://acme.atlassian.net/"), captured[0]["url"]
    assert captured[0]["authorization"] == _basic("ada@acme.example", "ACME-OWN-TOKEN")
    assert SERVER_TOKEN not in json.dumps(captured) and "server-wide" not in captured[0]["url"]


async def test_two_organizations_never_see_each_others_credentials(client, db_session, register_payload, captured):
    token_a, org_a = await _owner_and_org(client, db_session, register_payload["email"])
    token_b, org_b = await _owner_and_org(client, db_session, "bea@example.com")
    await client.put(f"/organizations/{org_a['id']}/connectors/jira", json={"fields": _jira(token="TOKEN-OF-A", base="https://a.atlassian.net")}, headers=_auth(token_a))

    refused = await client.post(f"/organizations/{org_b['id']}/crm/jira/import", json={"limit": 5}, headers=_auth(token_b))
    assert refused.status_code == 403
    assert captured == []

    await client.put(f"/organizations/{org_b['id']}/connectors/jira", json={"fields": _jira(token="TOKEN-OF-B", base="https://b.atlassian.net")}, headers=_auth(token_b))
    await client.post(f"/organizations/{org_b['id']}/crm/jira/import", json={"limit": 5}, headers=_auth(token_b))
    await client.post(f"/organizations/{org_a['id']}/crm/jira/import", json={"limit": 5}, headers=_auth(token_a))

    assert [c["url"].split("/")[2] for c in captured] == ["b.atlassian.net", "a.atlassian.net"]
    assert captured[0]["authorization"].endswith(_basic("ada@acme.example", "TOKEN-OF-B").split(" ")[1]) and "TOKEN-OF-A" not in captured[0]["authorization"]


async def test_removing_the_credentials_closes_the_door_again(client, db_session, register_payload, captured):
    token, org = await _owner_and_org(client, db_session, register_payload["email"])
    await client.put(f"/organizations/{org['id']}/connectors/jira", json={"fields": _jira()}, headers=_auth(token))
    assert (await client.delete(f"/organizations/{org['id']}/connectors/jira", headers=_auth(token))).status_code == 204
    assert (await client.post(f"/organizations/{org['id']}/crm/jira/import", json={"limit": 5}, headers=_auth(token))).status_code == 403
    assert (await client.delete(f"/organizations/{org['id']}/connectors/jira", headers=_auth(token))).status_code == 404


# ---------------------------------------------------------------- secrets


async def test_secrets_are_encrypted_at_rest_and_never_returned(client, db_session, register_payload):
    token, org = await _owner_and_org(client, db_session, register_payload["email"])
    put = await client.put(f"/organizations/{org['id']}/connectors/jira", json={"fields": _jira(token="PLAINTEXT-SECRET-123")}, headers=_auth(token))
    listing = await client.get(f"/organizations/{org['id']}/connectors", headers=_auth(token))

    assert "PLAINTEXT-SECRET-123" not in put.text and "PLAINTEXT-SECRET-123" not in listing.text
    jira = next(c for c in listing.json()["connectors"] if c["provider"] == "jira")
    assert jira["connected"] is True and jira["fields_set"] == ["JIRA_API_TOKEN", "JIRA_BASE_URL", "JIRA_EMAIL"]
    row = await db_session.scalar(select(ConnectorCredential).where(ConnectorCredential.organization_id == uuid.UUID(org["id"])))
    assert "PLAINTEXT-SECRET-123" not in row.encrypted_payload and "acme.atlassian.net" not in row.encrypted_payload
    assert listing.json()["platform_credentials_allowed"] is False


async def test_storing_credentials_without_an_encryption_key_is_refused_clearly(client, db_session, register_payload, monkeypatch):
    token, org = await _owner_and_org(client, db_session, register_payload["email"])
    monkeypatch.setattr(settings, "ENCRYPTION_MASTER_KEY", None)
    response = await client.put(f"/organizations/{org['id']}/connectors/jira", json={"fields": _jira()}, headers=_auth(token))
    assert response.status_code == 503 and "ENCRYPTION_MASTER_KEY" in response.text


# ---------------------------------------------------------------- who may do what


async def test_a_member_and_a_viewer_can_see_what_is_connected_but_cannot_write_credentials(client, db_session, register_payload):
    owner_token, org = await _owner_and_org(client, db_session, register_payload["email"])
    for email, role in (("member@example.com", OrganizationRole.member), ("viewer@example.com", OrganizationRole.viewer)):
        member_token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
        user = await db_session.scalar(select(User).where(User.email == email))
        db_session.add(OrganizationMember(organization_id=uuid.UUID(org["id"]), user_id=user.id, role=role))
        await db_session.commit()
        put = await client.put(f"/organizations/{org['id']}/connectors/jira", json={"fields": _jira()}, headers=_auth(member_token))
        assert put.status_code == 403, (email, put.text)
        listing = await client.get(f"/organizations/{org['id']}/connectors", headers=_auth(member_token))
        assert listing.status_code == 200, (email, listing.status_code)  # integrations:read: the list names fields, never values
    assert (await client.put(f"/organizations/{org['id']}/connectors/jira", json={"fields": _jira()}, headers=_auth(owner_token))).status_code == 200


async def test_an_outsider_cannot_touch_another_organizations_connectors(client, db_session, register_payload):
    _, org = await _owner_and_org(client, db_session, register_payload["email"])
    outsider = (await client.post("/auth/register", json={"email": "out@example.com", "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    assert (await client.get(f"/organizations/{org['id']}/connectors", headers=_auth(outsider))).status_code in (403, 404)
    assert (await client.put(f"/organizations/{org['id']}/connectors/jira", json={"fields": _jira()}, headers=_auth(outsider))).status_code in (403, 404)


# ---------------------------------------------------------------- validation of what a customer types


@pytest.mark.parametrize(
    "provider,fields",
    [
        ("jira", _jira(base="http://acme.atlassian.net")),                      # not https
        ("jira", _jira(base="https://user:pw@acme.atlassian.net")),             # credentials in the address
        ("jira", _jira(base="https://acme.atlassian.net:8443")),                # custom port
        ("jira", _jira(token="line1\r\nX-Injected: yes")),                      # header injection
        ("jira", {"JIRA_BASE_URL": "https://acme.atlassian.net"}),              # missing required fields
        ("jira", {**_jira(), "SOMETHING_ELSE": "x"}),                           # unknown field
        ("zendesk", {"ZENDESK_SUBDOMAIN": "evil.com/x#", "ZENDESK_EMAIL": "a@b.c", "ZENDESK_API_TOKEN": "t"}),
        ("zendesk", {"ZENDESK_SUBDOMAIN": "a.b", "ZENDESK_EMAIL": "a@b.c", "ZENDESK_API_TOKEN": "t"}),
        ("mailchimp", {"MAILCHIMP_DC": "x.evil.com", "MAILCHIMP_API_TOKEN": "t"}),
        ("mailchimp", {"MAILCHIMP_DC": "us21/../../x", "MAILCHIMP_API_TOKEN": "t"}),
        ("docusign", {"DOCUSIGN_ACCOUNT_ID": "../../admin", "DOCUSIGN_API_TOKEN": "t"}),
        ("salesforce", {"SALESFORCE_INSTANCE_URL": "https://evil.example.com", "SALESFORCE_CLIENT_ID": "i", "SALESFORCE_CLIENT_SECRET": "s"}),
        ("shopify", {"SHOPIFY_SHOP_DOMAIN": "shop.evil.com", "SHOPIFY_API_TOKEN": "t"}),
    ],
)
async def test_invalid_credentials_are_refused_with_422(client, db_session, register_payload, provider, fields):
    token, org = await _owner_and_org(client, db_session, register_payload["email"])
    response = await client.put(f"/organizations/{org['id']}/connectors/{provider}", json={"fields": fields}, headers=_auth(token))
    assert response.status_code == 422, response.text


async def test_an_unknown_connector_is_a_404(client, db_session, register_payload):
    token, org = await _owner_and_org(client, db_session, register_payload["email"])
    assert (await client.put(f"/organizations/{org['id']}/connectors/not-a-service", json={"fields": {"X": "y"}}, headers=_auth(token))).status_code == 404


@pytest.mark.parametrize("host", ["127.0.0.1", "169.254.169.254", "10.0.0.8", "192.168.1.5", "::1", "localhost"])
def test_a_host_that_resolves_to_a_private_address_is_refused(monkeypatch, host):
    """The real address check (the autouse fixture replaces it for the HTTP tests)."""
    import ipaddress
    import socket

    monkeypatch.undo()  # drop the stub of _public_host_or_raise
    address = "127.0.0.1" if host == "localhost" else host
    family = socket.AF_INET6 if ipaddress.ip_address(address).version == 6 else socket.AF_INET
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(family, socket.SOCK_STREAM, 6, "", (address, 443))])
    with pytest.raises(ValueError, match="public address"):
        cc._public_host_or_raise(host)


def test_a_public_address_is_accepted(monkeypatch):
    import socket

    monkeypatch.undo()
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    cc._public_host_or_raise("acme.atlassian.net")


def test_vendor_hosted_fields_stay_under_the_vendor_domain():
    zendesk = cc.validate_credentials("zendesk", {"ZENDESK_SUBDOMAIN": "Acme.zendesk.com", "ZENDESK_EMAIL": "a@b.c", "ZENDESK_API_TOKEN": "t"}, resolve=False)
    assert zendesk["ZENDESK_SUBDOMAIN"] == "acme"
    assert cc.validate_credentials("shopify", {"SHOPIFY_SHOP_DOMAIN": "acme", "SHOPIFY_API_TOKEN": "t"}, resolve=False)["SHOPIFY_SHOP_DOMAIN"] == "acme.myshopify.com"
    assert cc.validate_credentials("mailchimp", {"MAILCHIMP_DC": "us21", "MAILCHIMP_API_TOKEN": "t"}, resolve=False)["MAILCHIMP_DC"] == "us21"


# ---------------------------------------------------------------- the proxy and the legacy mode


def test_while_an_organization_scope_is_active_a_missing_field_is_none_not_the_servers_value():
    token = cc._active.set({"JIRA_EMAIL": "ada@acme.example"})
    try:
        assert connector_settings.JIRA_EMAIL == "ada@acme.example"
        assert connector_settings.JIRA_API_TOKEN is None  # the server has one, the organization did not give it
        assert connector_settings.JIRA_ENABLED is True    # non credential settings still come from the server
    finally:
        cc._active.reset(token)
    assert connector_settings.JIRA_API_TOKEN == SERVER_TOKEN  # scope reset: platform value visible again


async def test_the_scope_is_reset_after_a_request(client, db_session, register_payload, captured):
    token, org = await _owner_and_org(client, db_session, register_payload["email"])
    await client.put(f"/organizations/{org['id']}/connectors/jira", json={"fields": _jira()}, headers=_auth(token))
    await client.post(f"/organizations/{org['id']}/crm/jira/import", json={"limit": 5}, headers=_auth(token))
    assert cc._active.get() is None


async def test_the_legacy_shared_mode_still_works_when_the_operator_asks_for_it(client, db_session, register_payload, captured, monkeypatch):
    monkeypatch.setattr(settings, "CONNECTORS_ALLOW_PLATFORM_CREDENTIALS", True)
    token, org = await _owner_and_org(client, db_session, register_payload["email"])
    response = await client.post(f"/organizations/{org['id']}/crm/jira/import", json={"limit": 5}, headers=_auth(token))
    assert response.status_code == 200
    assert captured[0]["url"].startswith("https://server-wide.atlassian.net/")
    assert captured[0]["authorization"] == _basic("operator@example.com", SERVER_TOKEN)


async def test_github_works_without_credentials_for_public_data_but_never_with_the_servers_token(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_API_TOKEN", "SERVER-GITHUB-TOKEN")
    token, org = await _owner_and_org(client, db_session, register_payload["email"])
    async with cc.connector_scope_for(db_session, uuid.UUID(org["id"]), "github"):
        assert connector_settings.GITHUB_API_TOKEN is None
    await client.put(f"/organizations/{org['id']}/connectors/github", json={"fields": {"GITHUB_API_TOKEN": "ORG-GITHUB-TOKEN"}}, headers=_auth(token))
    async with cc.connector_scope_for(db_session, uuid.UUID(org["id"]), "github"):
        assert connector_settings.GITHUB_API_TOKEN == "ORG-GITHUB-TOKEN"


async def test_every_document_importer_and_crm_route_is_guarded(client, db_session, register_payload):
    """No import route may stay reachable with the server's credentials: each of them is refused for an organization that connected nothing."""
    token, org = await _owner_and_org(client, db_session, register_payload["email"])
    base = f"/organizations/{org['id']}"
    attempts = {
        "documents/notion": {"url_or_id": "abc"}, "documents/confluence": {"url_or_id": "12345"},
        "documents/google-drive": {"drive_id": "abc"}, "documents/google-docs": {"document_url_or_id": "abc"}, "documents/onedrive": {"folder_id": "abc"},
    }
    for path, body in attempts.items():
        response = await client.post(f"{base}/{path}", json=body, headers=_auth(token))
        assert response.status_code == 403, (path, response.status_code, response.text[:120])
    # all 36 CRM routes
    from api.main import app

    crm_paths = sorted(path for path in app.openapi()["paths"] if path.startswith("/organizations/{org_id}/crm/"))
    assert len(crm_paths) == 36
    for path in crm_paths:
        response = await client.post(path.replace("{org_id}", org["id"]), json={"limit": 1}, headers=_auth(token))
        assert response.status_code in (400, 403), (path, response.status_code)
        if response.status_code == 400:  # switched off by the operator: refused before any credential is looked at
            assert "disabled" in response.text.lower() or "not enabled" in response.text.lower(), (path, response.text[:120])


# ---------------------------------------------------------------- background tasks (PostgreSQL, because a task opens its own engine)


@pytest.fixture
async def pg_org():
    """A real PostgreSQL organization, only on a local database whose name contains 'pytest' or 'test'."""
    url = make_url(settings.DATABASE_URL)
    if "postgresql" not in url.drivername or url.host not in ("127.0.0.1", "localhost") or "test" not in (url.database or ""):
        pytest.skip("needs a local PostgreSQL TEST_DATABASE_URL")
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            has_table = await connection.scalar(text("select to_regclass('public.connector_credentials')"))
    except Exception:
        await engine.dispose()
        pytest.skip("PostgreSQL is not reachable")
    if has_table is None:
        await engine.dispose()
        pytest.skip("migration 0143 is not applied on this database")
    from api.models.organization import Organization

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with factory() as db:
        organization = Organization(name="Task Org", slug=f"task-org-{uuid.uuid4().hex[:8]}")
        db.add(organization)
        await db.commit()
        org_id = organization.id
    yield factory, org_id
    async with factory() as db:
        await db.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": org_id})
        await db.commit()
    await engine.dispose()


async def test_a_background_task_runs_with_the_credentials_stored_for_its_organization(pg_org):
    factory, org_id = pg_org
    async with factory() as db:
        await cc.save_credentials(db, org_id, "jira", cc.validate_credentials("jira", _jira(token="TASK-ORG-TOKEN"), resolve=False), None)
        await db.commit()

    async def read():
        return connector_settings.JIRA_API_TOKEN, connector_settings.JIRA_BASE_URL

    assert await cc.run_in_scope("jira", org_id, read) == ("TASK-ORG-TOKEN", "https://acme.atlassian.net")
    assert connector_settings.JIRA_API_TOKEN == SERVER_TOKEN  # reset afterwards


async def test_a_background_task_for_an_organization_without_credentials_is_refused(pg_org):
    from fastapi import HTTPException

    _factory, org_id = pg_org

    async def read():  # pragma: no cover -- must not run
        raise AssertionError("ran with the server's credentials")

    with pytest.raises(HTTPException) as refused:
        await cc.run_in_scope("jira", org_id, read)
    assert refused.value.status_code == 403
    # ...but public GitHub data still works, without any token
    async def github_token():
        return connector_settings.GITHUB_API_TOKEN

    assert await cc.run_in_scope("github", org_id, github_token) is None


# a guard against forgetting a connector: every provider declared in the table has exactly the fields its module reads
def test_every_credential_field_of_the_table_is_a_real_setting():
    for provider, fields in cc.PROVIDERS.items():
        for field in fields:
            assert hasattr(settings, field.name), (provider, field.name)
