"""
Partie 1.4.6 -- white-label. Fast SQLite suite, same tier as
tests/test_organization_branding.py. No real network dependency here
(unlike branding's own logo/favicon upload tests) -- white-label is
just a boolean living on the same organization_branding row.
"""

import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.organization_branding import OrganizationBranding
from api.models.user import User
from api.security.white_label import get_white_label_config, is_white_label_enabled


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


# --------------------------------------------------------------- defaults --

async def test_white_label_defaults_to_disabled(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.get(f"/organizations/{org['id']}/white-label", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["hide_platform_branding"] is False
    assert body["organization_id"] == org["id"]


async def test_get_white_label_config_includes_the_full_branding_dict(client, db_session, register_payload):
    """Validation criterion: white-label is correctly returned --
    including the branding fields it's paired with, not just the flag
    on its own (see api/security/white_label.py's own docstring on why
    white-label config IS branding config)."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.get(f"/organizations/{org['id']}/white-label", headers=_auth_header(owner_token))
    body = response.json()
    for key in ("logo_url", "favicon_url", "primary_color", "secondary_color", "accent_color", "font_family", "brand_name", "custom_css"):
        assert key in body


# --------------------------------------------------------------- toggling --

async def test_owner_can_enable_white_label(client, db_session, register_payload):
    """Validation criterion: an Owner can enable/disable white-label."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/white-label", json={"hide_platform_branding": True}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["hide_platform_branding"] is True

    row = await db_session.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id == uuid.UUID(org["id"])))
    assert row.hide_platform_branding is True


async def test_owner_can_disable_white_label_after_enabling_it(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    await client.patch(f"/organizations/{org['id']}/white-label", json={"hide_platform_branding": True}, headers=_auth_header(owner_token))
    response = await client.patch(
        f"/organizations/{org['id']}/white-label", json={"hide_platform_branding": False}, headers=_auth_header(owner_token),
    )
    assert response.json()["hide_platform_branding"] is False


async def test_patching_with_no_fields_leaves_white_label_unchanged(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.patch(f"/organizations/{org['id']}/white-label", json={"hide_platform_branding": True}, headers=_auth_header(owner_token))

    response = await client.patch(f"/organizations/{org['id']}/white-label", json={}, headers=_auth_header(owner_token))
    assert response.json()["hide_platform_branding"] is True  # untouched


async def test_toggling_white_label_does_not_change_other_branding_fields(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.patch(f"/organizations/{org['id']}/branding", json={"brand_name": "Acme Corp"}, headers=_auth_header(owner_token))

    response = await client.patch(f"/organizations/{org['id']}/white-label", json={"hide_platform_branding": True}, headers=_auth_header(owner_token))
    assert response.json()["brand_name"] == "Acme Corp"  # untouched by the white-label endpoint


# --------------------------------------------------------------- permissions --

async def test_admin_cannot_modify_white_label(client, db_session, register_payload):
    """Validation criterion: an Admin cannot modify white-label."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin = await _register(client, db_session, "whitelabeladmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.patch(
        f"/organizations/{org['id']}/white-label", json={"hide_platform_branding": True}, headers=_auth_header(admin_token),
    )
    assert response.status_code == 403


async def test_admin_cannot_view_white_label(client, db_session, register_payload):
    """Unlike GET .../branding (deliberately public), GET .../white-label
    is Owner-only -- this is an admin-facing configuration view, not
    something a visitor or even a non-Owner member needs."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin = await _register(client, db_session, "whitelabelviewadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/white-label", headers=_auth_header(admin_token))
    assert response.status_code == 403


async def test_non_member_cannot_view_white_label(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    outsider_token, outsider = await _register(client, db_session, "whitelabeloutsider@example.com")
    response = await client.get(f"/organizations/{org['id']}/white-label", headers=_auth_header(outsider_token))
    assert response.status_code == 404  # anti-enumeration, same convention as every other org-scoped route


async def test_white_label_requires_authentication(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.get(f"/organizations/{org['id']}/white-label")  # no Authorization header
    assert response.status_code in (401, 403)


# ------------------------------------------------------------- 404 handling --

async def test_white_label_for_a_nonexistent_organization_returns_404(client, register_payload, db_session):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.get(f"/organizations/{uuid.uuid4()}/white-label", headers=_auth_header(owner_token))
    assert response.status_code == 404


# --------------------------------------------------------- security-layer logic --

async def test_is_white_label_enabled_reflects_the_stored_flag(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    assert await is_white_label_enabled(db_session, org_id) is False

    await client.patch(f"/organizations/{org['id']}/white-label", json={"hide_platform_branding": True}, headers=_auth_header(owner_token))
    assert await is_white_label_enabled(db_session, org_id) is True


async def test_get_white_label_config_matches_get_org_branding(client, db_session, register_payload):
    """White-label config IS branding config -- see
    api/security/white_label.py's own docstring."""
    from api.security.organization_branding import get_org_branding

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    white_label = await get_white_label_config(db_session, org_id)
    branding = await get_org_branding(db_session, org_id)
    assert white_label == branding


# ------------------------------------------------------ coherence with 1.3.10 --

async def test_hide_platform_branding_is_also_visible_through_the_public_branding_endpoint(client, db_session, register_payload):
    """Vision critique Q1 -- coherence with existing branding (1.3.10):
    hide_platform_branding is one field of the SAME branding row, so it
    must also surface through the pre-existing public GET .../branding,
    not only the new Owner-only white-label endpoint."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.patch(f"/organizations/{org['id']}/white-label", json={"hide_platform_branding": True}, headers=_auth_header(owner_token))

    response = await client.get(f"/organizations/{org['id']}/branding")  # public, no auth
    assert response.status_code == 200
    assert response.json()["hide_platform_branding"] is True
