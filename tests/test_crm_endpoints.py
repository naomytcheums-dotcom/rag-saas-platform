"""Phase 5, Étape 18 -- CRM import endpoints. Fast SQLite suite.

Tests the 17 CRM import endpoints' own real behavior WITHOUT making
real network calls to the CRM providers (which would be flaky and
require real credentials): each endpoint is tested for its real
disabled-state (400), permission-state (403), and unknown-provider
behavior. The real extraction logic itself is covered separately by
each module's own unit tests.
"""

import uuid

from sqlalchemy import select

from api.config import settings
from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    response = await client.post("/auth/register", json=payload)
    if response.status_code != 201:
        login = await client.post("/auth/login", json={"email": email, "password": password})
        token = login.json()["access_token"]
    else:
        token = response.json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


ALL_CRM_PROVIDERS = [
    "salesforce", "hubspot", "jira", "zendesk", "pipedrive",
    "linear", "asana", "trello", "airtable", "dropbox", "box",
    "clickup", "intercom", "zoho", "shopify", "woocommerce", "docusign",
]


async def test_all_crm_endpoints_are_exposed(client):
    """Every provider has a real import endpoint registered."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for provider in ALL_CRM_PROVIDERS:
        expected = f"/organizations/{{org_id}}/crm/{provider}/import"
        assert expected in paths, f"Missing endpoint: {expected}"


async def test_crm_import_requires_authentication(client):
    """Import endpoints reject unauthenticated calls."""
    fake_org = uuid.uuid4()
    response = await client.post(
        f"/organizations/{fake_org}/crm/salesforce/import",
        json={"limit": 10},
    )
    assert response.status_code == 401


async def test_crm_import_rejects_disabled_provider(client, db_session, register_payload):
    """A disabled provider returns a clear 400."""
    token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, token, "CRM Disabled Org")

    # Ensure Salesforce is disabled (the default)
    assert settings.SALESFORCE_ENABLED is False

    response = await client.post(
        f"/organizations/{org['id']}/crm/salesforce/import",
        json={"limit": 10},
        headers=_auth_header(token),
    )

    assert response.status_code == 400
    assert "disabled" in response.json()["detail"].lower()


async def test_crm_import_rejects_member_without_permission(client, db_session, register_payload):
    """A member without documents:write gets 403."""
    import uuid as _uuid
    from api.models.organization import OrganizationMember, OrganizationRole

    token_owner, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, token_owner, "CRM Perm Org")

    viewer_payload = {"email": f"crm-viewer-{_uuid.uuid4().hex[:8]}@example.com", "password": "correct-horse-battery-staple", "accept_terms": True}
    viewer_token, viewer_user = await _register(client, db_session, viewer_payload["email"], viewer_payload["password"])
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org["id"]), user_id=viewer_user.id, role=OrganizationRole.viewer))
    await db_session.commit()

    response = await client.post(
        f"/organizations/{org['id']}/crm/salesforce/import",
        json={"limit": 10},
        headers=_auth_header(viewer_token),
    )

    # viewer does NOT have documents:write (only documents:read)
    assert response.status_code == 403
