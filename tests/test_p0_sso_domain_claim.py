"""
SADM-001 (P0): a platform admin must not be able to claim an email domain
for an IdP of their choosing. Connection creation / domain verification is
superadmin-only, and a connection routes logins only once its domain's
ownership is proven (DNS TXT). Everything external (DNS, IdP metadata) is
simulated.
"""

import uuid

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.enterprise_sso import EnterpriseSSOConnection
from api.models.user import User, UserRole

pytestmark = pytest.mark.asyncio

_PASSWORD = "correct-horse-battery-staple"
_ISSUER = "https://idp.example.test"


@pytest.fixture(autouse=True)
def _secret_key_and_idp_metadata(monkeypatch):
    if not settings.SECRET_ENCRYPTION_KEY:
        from cryptography.fernet import Fernet
        monkeypatch.setattr(settings, "SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr("api.routers.enterprise_sso.send_enterprise_sso_connection_created_email", lambda *a: None)

    async def _fake_metadata(_issuer):
        return {"authorization_endpoint": f"{_ISSUER}/authorize", "token_endpoint": f"{_ISSUER}/token"}

    monkeypatch.setattr("api.routers.enterprise_sso.fetch_oidc_metadata", _fake_metadata)


@pytest.fixture
def dns_txt(monkeypatch):
    """Simulated DNS: the set of (domain, token) pairs that publish the TXT challenge."""
    published: set[tuple[str, str]] = set()

    async def _check(domain, token):
        return (domain, token) in published

    monkeypatch.setattr("api.routers.enterprise_sso.check_email_verification_txt_record", _check)
    return published


async def _account(client, db_session, role: UserRole | None) -> dict:
    email = f"sso-{uuid.uuid4().hex[:10]}@example.com"
    registered = await client.post("/auth/register", json={"email": email, "password": _PASSWORD, "accept_terms": True})
    assert registered.status_code == 201, registered.text
    if role is not None:
        user = await db_session.scalar(select(User).where(User.email == email))
        user.role = role
        await db_session.commit()
    return {"Authorization": f"Bearer {registered.json()['access_token']}"}


def _body(domain: str) -> dict:
    return {"email_domain": domain, "display_name": "Victim Corp SSO", "issuer": _ISSUER, "client_id": "cid", "client_secret": "csecret"}


async def _connection_count(db_session) -> int:
    return len((await db_session.scalars(select(EnterpriseSSOConnection))).all())


async def test_platform_admin_cannot_create_a_connection(client, db_session):
    admin = await _account(client, db_session, UserRole.admin)
    response = await client.post("/admin/sso/connections", json=_body("victim-corp.com"), headers=admin)
    assert response.status_code == 403
    assert await _connection_count(db_session) == 0


async def test_regular_user_cannot_create_a_connection(client, db_session):
    user = await _account(client, db_session, None)
    response = await client.post("/admin/sso/connections", json=_body("victim-corp.com"), headers=user)
    assert response.status_code == 403
    assert await _connection_count(db_session) == 0


async def test_platform_admin_cannot_verify_or_activate_a_domain(client, db_session, dns_txt):
    superadmin = await _account(client, db_session, UserRole.superadmin)
    created = (await client.post("/admin/sso/connections", json=_body("victim-corp.com"), headers=superadmin)).json()
    dns_txt.add(("victim-corp.com", created["domain_verification_token"]))

    admin = await _account(client, db_session, UserRole.admin)
    response = await client.post(f"/admin/sso/connections/{created['id']}/verify-domain", headers=admin)
    assert response.status_code == 403

    row = await db_session.get(EnterpriseSSOConnection, uuid.UUID(created["id"]))
    await db_session.refresh(row)
    assert row.domain_verified is False


async def test_superadmin_can_create_a_connection_which_starts_unverified(client, db_session):
    superadmin = await _account(client, db_session, UserRole.superadmin)
    response = await client.post("/admin/sso/connections", json=_body("legit-corp.com"), headers=superadmin)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email_domain"] == "legit-corp.com"
    assert body["domain_verified"] is False
    assert body["domain_verification_token"]
    assert "client_secret" not in body


async def test_unverified_domain_is_never_used_to_route_a_login(client, db_session):
    victim_email = f"victim-{uuid.uuid4().hex[:8]}@victim-corp.com"
    await client.post("/auth/register", json={"email": victim_email, "password": _PASSWORD, "accept_terms": True})

    superadmin = await _account(client, db_session, UserRole.superadmin)
    created = (await client.post("/admin/sso/connections", json=_body("victim-corp.com"), headers=superadmin)).json()

    discover = await client.post("/auth/sso/discover", json={"email": victim_email})
    assert discover.status_code == 200
    assert discover.json() == {"sso_available": False, "connection_id": None, "display_name": None}

    authorize = await client.get(f"/auth/sso/{created['id']}/authorize")
    assert authorize.status_code == 404


async def test_password_login_is_unchanged_for_an_unverified_domain(client, db_session):
    email = f"pw-{uuid.uuid4().hex[:8]}@victim-corp.com"
    await client.post("/auth/register", json={"email": email, "password": _PASSWORD, "accept_terms": True})
    superadmin = await _account(client, db_session, UserRole.superadmin)
    await client.post("/admin/sso/connections", json=_body("victim-corp.com"), headers=superadmin)

    login = await client.post("/auth/login", json={"email": email, "password": _PASSWORD})
    assert login.status_code == 200, login.text
    assert login.json()["access_token"]


async def test_verification_fails_without_the_dns_record(client, db_session, dns_txt):
    superadmin = await _account(client, db_session, UserRole.superadmin)
    created = (await client.post("/admin/sso/connections", json=_body("victim-corp.com"), headers=superadmin)).json()

    response = await client.post(f"/admin/sso/connections/{created['id']}/verify-domain", headers=superadmin)
    assert response.status_code == 409

    discover = await client.post("/auth/sso/discover", json={"email": "someone@victim-corp.com"})
    assert discover.json()["sso_available"] is False


async def test_verified_domain_routes_the_login(client, db_session, dns_txt):
    superadmin = await _account(client, db_session, UserRole.superadmin)
    created = (await client.post("/admin/sso/connections", json=_body("legit-corp.com"), headers=superadmin)).json()
    dns_txt.add(("legit-corp.com", created["domain_verification_token"]))

    verified = await client.post(f"/admin/sso/connections/{created['id']}/verify-domain", headers=superadmin)
    assert verified.status_code == 200, verified.text
    assert verified.json()["domain_verified"] is True

    discover = await client.post("/auth/sso/discover", json={"email": "someone@legit-corp.com"})
    assert discover.json() == {"sso_available": True, "connection_id": created["id"], "display_name": "Victim Corp SSO"}

    authorize = await client.get(f"/auth/sso/{created['id']}/authorize")
    assert authorize.status_code == 302
    assert authorize.headers["location"].startswith(f"{_ISSUER}/authorize")


async def test_callback_is_refused_if_the_domain_is_not_verified(client, db_session, dns_txt):
    superadmin = await _account(client, db_session, UserRole.superadmin)
    created = (await client.post("/admin/sso/connections", json=_body("legit-corp.com"), headers=superadmin)).json()
    dns_txt.add(("legit-corp.com", created["domain_verification_token"]))
    await client.post(f"/admin/sso/connections/{created['id']}/verify-domain", headers=superadmin)

    authorize = await client.get(f"/auth/sso/{created['id']}/authorize")
    state = authorize.headers["location"].split("state=")[1].split("&")[0]

    row = await db_session.get(EnterpriseSSOConnection, uuid.UUID(created["id"]))
    row.domain_verified = False
    await db_session.commit()

    callback = await client.get(f"/auth/sso/{created['id']}/callback", params={"code": "forged", "state": state})
    assert callback.status_code == 404
