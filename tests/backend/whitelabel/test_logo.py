"""Partie 19 -- POST/DELETE .../whitelabel/logo, POST .../whitelabel/favicon.
Real upload/storage validation already lives in
api/services/storage.py (tested there and in
tests/test_organization_branding.py) -- monkeypatched here the same
way, so this file tests the white-label-specific plumbing (delegation,
delete-previous-on-replace, response shape), not S3 itself."""

from sqlalchemy import select

from api.models.organization_branding import OrganizationBranding
from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def test_logo_upload_succeeds_and_updates_config(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.white_label.upload_organization_logo", lambda org_id, content: "https://cdn.example.com/branding/logo-abc.png")

    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(f"/organizations/{org['id']}/whitelabel/logo", files={"file": ("logo.png", b"fake-bytes", "image/png")}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["logo_url"] == "https://cdn.example.com/branding/logo-abc.png"


async def test_replacing_a_logo_deletes_the_previous_one(client, db_session, register_payload, monkeypatch):
    deleted = []
    monkeypatch.setattr("api.security.white_label.upload_organization_logo", lambda org_id, content: "https://cdn.example.com/branding/first.png")
    monkeypatch.setattr("api.security.white_label.delete_branding_asset", lambda url: deleted.append(url))

    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/whitelabel/logo", files={"file": ("logo.png", b"fake-bytes", "image/png")}, headers=_auth_header(owner_token))

    monkeypatch.setattr("api.security.white_label.upload_organization_logo", lambda org_id, content: "https://cdn.example.com/branding/second.png")
    response = await client.post(f"/organizations/{org['id']}/whitelabel/logo", files={"file": ("logo2.png", b"more-bytes", "image/png")}, headers=_auth_header(owner_token))
    assert response.json()["logo_url"] == "https://cdn.example.com/branding/second.png"
    assert deleted == ["https://cdn.example.com/branding/first.png"]


async def test_logo_upload_translates_a_validation_error_into_400(client, db_session, register_payload, monkeypatch):
    def _raise(org_id, content):
        raise ValueError("file too large")

    monkeypatch.setattr("api.security.white_label.upload_organization_logo", _raise)

    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(f"/organizations/{org['id']}/whitelabel/logo", files={"file": ("logo.png", b"x", "image/png")}, headers=_auth_header(owner_token))
    assert response.status_code == 400


async def test_delete_logo_clears_the_url(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.white_label.upload_organization_logo", lambda org_id, content: "https://cdn.example.com/branding/logo-abc.png")
    monkeypatch.setattr("api.security.white_label.delete_branding_asset", lambda url: None)

    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/whitelabel/logo", files={"file": ("logo.png", b"x", "image/png")}, headers=_auth_header(owner_token))

    response = await client.delete(f"/organizations/{org['id']}/whitelabel/logo", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["logo_url"] is None


async def test_favicon_upload_succeeds_and_updates_config(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.white_label.upload_organization_favicon", lambda org_id, content: "https://cdn.example.com/branding/favicon-abc.ico")

    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(f"/organizations/{org['id']}/whitelabel/favicon", files={"file": ("favicon.ico", b"x", "image/x-icon")}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["favicon_url"] == "https://cdn.example.com/branding/favicon-abc.ico"


async def test_admin_cannot_upload_logo_for_a_non_admin_role(client, db_session, register_payload):
    """Member (not Admin/Owner) is rejected -- these endpoints are
    Admin+, one tier laxer than the pre-existing branding upload
    endpoints (Owner-only), a deliberate, documented difference."""
    from api.models.organization import OrganizationMember, OrganizationRole
    import uuid

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "wl_logo_member@example.com")
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org["id"]), user_id=member.id, role=OrganizationRole.member, invited_by=owner.id))
    await db_session.commit()

    response = await client.post(f"/organizations/{org['id']}/whitelabel/logo", files={"file": ("logo.png", b"x", "image/png")}, headers=_auth_header(member_token))
    assert response.status_code == 403
