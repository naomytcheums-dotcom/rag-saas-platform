"""
Partie 1.3.10 -- per-organization branding. Fast SQLite suite, same
tier as tests/test_quotas.py. Upload/delete endpoints are tested here
against MONKEYPATCHED storage functions (permission/wiring logic only,
same pattern as tests/test_auth_api.py's avatar-upload error-translation
tests) -- the real validation logic (real image decoding, dimensions)
is covered in tests/test_storage.py, and the real end-to-end path
against a real S3-compatible bucket in
tests/test_branding_storage_integration.py.
"""

import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.organization_branding import OrganizationBranding
from api.models.user import User
from api.security.organization_branding import DEFAULT_BRANDING


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

async def test_default_branding_is_created_with_the_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    row = await db_session.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id == uuid.UUID(org["id"])))
    assert row is not None
    assert row.primary_color == DEFAULT_BRANDING["primary_color"]
    assert row.logo_url is None


async def test_get_branding_returns_every_documented_default(client, register_payload, db_session):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.get(f"/organizations/{org['id']}/branding")
    assert response.status_code == 200
    body = response.json()
    for key, value in DEFAULT_BRANDING.items():
        assert body[key] == value


# ------------------------------------------------------- public GET access --

async def test_get_branding_requires_no_authentication(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.get(f"/organizations/{org['id']}/branding")  # no Authorization header at all
    assert response.status_code == 200


async def test_get_branding_for_a_nonexistent_organization_returns_404(client):
    response = await client.get(f"/organizations/{uuid.uuid4()}/branding")
    assert response.status_code == 404


async def test_anyone_can_view_a_non_members_branding(client, db_session, register_payload):
    """The one deliberate exception to this codebase's usual
    anti-enumeration posture -- see api/routers/organization_branding.py's
    own docstring for why."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    outsider_token, outsider = await _register(client, db_session, "brandingoutsider@example.com")
    response = await client.get(f"/organizations/{org['id']}/branding", headers=_auth_header(outsider_token))
    assert response.status_code == 200


# --------------------------------------------------------------- writing --

async def test_owner_can_update_branding(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/branding", json={"primary_color": "#ff0000", "brand_name": "Acme Corp"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["primary_color"] == "#ff0000"
    assert body["brand_name"] == "Acme Corp"


async def test_admin_cannot_update_branding(client, db_session, register_payload):
    """Validation criterion: an Admin cannot modify branding -- Owner only."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin = await _register(client, db_session, "brandingadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.patch(
        f"/organizations/{org['id']}/branding", json={"primary_color": "#ff0000"}, headers=_auth_header(admin_token),
    )
    assert response.status_code == 403


async def test_updating_one_field_leaves_others_at_their_default(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/branding", json={"font_family": "Roboto"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["font_family"] == "Roboto"
    assert body["primary_color"] == DEFAULT_BRANDING["primary_color"]  # untouched


async def test_a_non_member_cannot_update_branding(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    outsider_token, outsider = await _register(client, db_session, "brandingpatchoutsider@example.com")
    response = await client.patch(
        f"/organizations/{org['id']}/branding", json={"primary_color": "#ff0000"}, headers=_auth_header(outsider_token),
    )
    assert response.status_code == 404  # anti-enumeration -- PATCH is NOT public, unlike GET


# ------------------------------------------------------------- validation --

async def test_invalid_hex_color_is_rejected(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/branding", json={"primary_color": "red"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 422


async def test_custom_css_with_a_dangerous_pattern_is_rejected(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/branding", json={"custom_css": "body { background: url('javascript:alert(1)') }"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 422


async def test_valid_custom_css_is_accepted(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/branding", json={"custom_css": ".header { font-weight: bold; }"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["custom_css"] == ".header { font-weight: bold; }"


# --------------------------------------------------------------- uploads --

async def test_logo_upload_translates_a_validation_error_into_400(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    def _raise(*args, **kwargs):
        raise ValueError("logo exceeds the 2048KB limit")

    monkeypatch.setattr("api.routers.organization_branding.upload_organization_logo", _raise)
    response = await client.post(
        f"/organizations/{org['id']}/branding/logo", headers=_auth_header(owner_token),
        files={"file": ("logo.png", b"not a real image", "image/png")},
    )
    assert response.status_code == 400


async def test_logo_upload_translates_a_storage_failure_into_502(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    def _raise(*args, **kwargs):
        raise RuntimeError("logo upload failed: simulated S3 outage")

    monkeypatch.setattr("api.routers.organization_branding.upload_organization_logo", _raise)
    response = await client.post(
        f"/organizations/{org['id']}/branding/logo", headers=_auth_header(owner_token),
        files={"file": ("logo.png", b"irrelevant", "image/png")},
    )
    assert response.status_code == 502


async def test_logo_upload_succeeds_and_updates_branding(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    monkeypatch.setattr("api.routers.organization_branding.upload_organization_logo", lambda org_id, content: "https://cdn.example.com/branding/logo-abc.png")

    response = await client.post(
        f"/organizations/{org['id']}/branding/logo", headers=_auth_header(owner_token),
        files={"file": ("logo.png", b"irrelevant -- upload_organization_logo itself is mocked", "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["logo_url"] == "https://cdn.example.com/branding/logo-abc.png"


async def test_replacing_a_logo_deletes_the_previous_one_from_storage(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    monkeypatch.setattr("api.routers.organization_branding.upload_organization_logo", lambda org_id, content: "https://cdn.example.com/branding/first.png")
    first = await client.post(
        f"/organizations/{org['id']}/branding/logo", headers=_auth_header(owner_token),
        files={"file": ("logo.png", b"irrelevant", "image/png")},
    )
    assert first.status_code == 200

    deleted_urls = []
    monkeypatch.setattr("api.routers.organization_branding.upload_organization_logo", lambda org_id, content: "https://cdn.example.com/branding/second.png")
    monkeypatch.setattr("api.routers.organization_branding.delete_branding_asset", lambda url: deleted_urls.append(url))
    second = await client.post(
        f"/organizations/{org['id']}/branding/logo", headers=_auth_header(owner_token),
        files={"file": ("logo.png", b"irrelevant", "image/png")},
    )
    assert second.status_code == 200
    assert second.json()["logo_url"] == "https://cdn.example.com/branding/second.png"
    assert deleted_urls == ["https://cdn.example.com/branding/first.png"]


async def test_favicon_upload_succeeds_and_updates_branding(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    monkeypatch.setattr("api.routers.organization_branding.upload_organization_favicon", lambda org_id, content: "https://cdn.example.com/branding/favicon-abc.ico")

    response = await client.post(
        f"/organizations/{org['id']}/branding/favicon", headers=_auth_header(owner_token),
        files={"file": ("favicon.png", b"irrelevant", "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["favicon_url"] == "https://cdn.example.com/branding/favicon-abc.ico"


async def test_admin_cannot_upload_logo(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin = await _register(client, db_session, "brandinguploadadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/branding/logo", headers=_auth_header(admin_token),
        files={"file": ("logo.png", b"irrelevant", "image/png")},
    )
    assert response.status_code == 403


# -------------------------------------------------------------- deletion --

async def test_deleting_a_logo_clears_the_url_and_calls_storage_delete(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    monkeypatch.setattr("api.routers.organization_branding.upload_organization_logo", lambda org_id, content: "https://cdn.example.com/branding/logo-abc.png")
    await client.post(
        f"/organizations/{org['id']}/branding/logo", headers=_auth_header(owner_token),
        files={"file": ("logo.png", b"irrelevant", "image/png")},
    )

    deleted_urls = []
    monkeypatch.setattr("api.routers.organization_branding.delete_branding_asset", lambda url: deleted_urls.append(url))

    response = await client.delete(f"/organizations/{org['id']}/branding/logo", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["logo_url"] is None
    assert deleted_urls == ["https://cdn.example.com/branding/logo-abc.png"]


async def test_deleting_a_logo_that_was_never_set_is_a_no_op(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    deleted_urls = []
    monkeypatch.setattr("api.routers.organization_branding.delete_branding_asset", lambda url: deleted_urls.append(url))

    response = await client.delete(f"/organizations/{org['id']}/branding/logo", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["logo_url"] is None
    assert deleted_urls == []  # nothing to delete -- storage was never called


async def test_deleting_a_favicon_clears_the_url(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    monkeypatch.setattr("api.routers.organization_branding.upload_organization_favicon", lambda org_id, content: "https://cdn.example.com/branding/favicon-abc.ico")
    await client.post(
        f"/organizations/{org['id']}/branding/favicon", headers=_auth_header(owner_token),
        files={"file": ("favicon.png", b"irrelevant", "image/png")},
    )

    monkeypatch.setattr("api.routers.organization_branding.delete_branding_asset", lambda url: None)
    response = await client.delete(f"/organizations/{org['id']}/branding/favicon", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["favicon_url"] is None


async def test_admin_cannot_delete_logo(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin = await _register(client, db_session, "brandingdeleteadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.delete(f"/organizations/{org['id']}/branding/logo", headers=_auth_header(admin_token))
    assert response.status_code == 403
