"""Partie 19 -- GET/PATCH /organizations/{org_id}/whitelabel/config,
GET .../preview, POST .../reset. Same fast SQLite tier as
tests/test_white_label.py/tests/test_organization_branding.py."""

import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
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


async def _add_member(db_session, org_id, user_id, role: OrganizationRole, invited_by=None):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


async def test_get_config_returns_defaults_including_domain_fields(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.get(f"/organizations/{org['id']}/whitelabel/config", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["is_active"] is True
    assert body["domain"] is None
    assert body["domain_verified"] is False
    assert body["custom_js"] is None
    assert body["company_email"] is None


async def test_member_can_view_but_not_update_config(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "wl_member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    view = await client.get(f"/organizations/{org['id']}/whitelabel/config", headers=_auth_header(member_token))
    assert view.status_code == 200

    update = await client.patch(f"/organizations/{org['id']}/whitelabel/config", json={"brand_name": "Nope"}, headers=_auth_header(member_token))
    assert update.status_code == 403


async def test_admin_can_update_config(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    admin_token, admin = await _register(client, db_session, "wl_admin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.patch(
        f"/organizations/{org['id']}/whitelabel/config",
        json={"brand_name": "Acme Corp", "primary_color": "#112233", "custom_js": "console.log('hi')"},
        headers=_auth_header(admin_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["brand_name"] == "Acme Corp"
    assert body["primary_color"] == "#112233"
    assert body["custom_js"] == "console.log('hi')"


async def test_custom_js_over_the_length_limit_is_rejected(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/whitelabel/config", json={"custom_js": "x" * 20_001}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 422


async def test_reset_restores_branding_defaults_but_keeps_logo(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.patch(f"/organizations/{org['id']}/whitelabel/config", json={"brand_name": "Acme Corp"}, headers=_auth_header(owner_token))

    from api.models.organization_branding import OrganizationBranding
    row = await db_session.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id == uuid.UUID(org["id"])))
    row.logo_url = "https://example.com/logo.png"
    await db_session.commit()

    response = await client.post(f"/organizations/{org['id']}/whitelabel/reset", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["brand_name"] is None
    assert body["logo_url"] == "https://example.com/logo.png"  # untouched by reset, see reset_whitelabel's own docstring


async def test_preview_reflects_is_active_kill_switch(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.patch(f"/organizations/{org['id']}/whitelabel/config", json={"brand_name": "Acme Corp"}, headers=_auth_header(owner_token))

    active_preview = await client.get(f"/organizations/{org['id']}/whitelabel/preview", headers=_auth_header(owner_token))
    assert active_preview.json()["brand_name"] == "Acme Corp"

    await client.patch(f"/organizations/{org['id']}/whitelabel/config", json={"is_active": False}, headers=_auth_header(owner_token))
    inactive_preview = await client.get(f"/organizations/{org['id']}/whitelabel/preview", headers=_auth_header(owner_token))
    assert inactive_preview.json()["brand_name"] is None  # real platform default, custom name suppressed
