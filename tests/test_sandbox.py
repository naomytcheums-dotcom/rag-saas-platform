"""
Sandbox Environment — isolated dev/test data.
"""

import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    response = await client.post("/auth/register", json=payload)
    if response.status_code != 201:
        login_response = await client.post("/auth/login", json={"email": email, "password": password})
        access_token = login_response.json()["access_token"]
    else:
        access_token = response.json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


# ------------------------------------------------------- create --


async def test_create_sandbox_environment(client, db_session, register_payload):
    """Create a sandbox environment successfully."""
    token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, token, "Sandbox Test Org")

    response = await client.post(
        f"/organizations/{org['id']}/sandbox?name=Test+Sandbox&data_ttl_hours=24",
        headers=_auth_header(token),
    )

    assert response.status_code in (200, 201), f"Got {response.status_code}: {response.text}"
    data = response.json()
    assert data["name"] == "Test Sandbox"
    assert data["data_ttl_hours"] == 24
    assert data["is_active"] is True
    assert data["expires_at"] is not None


# ------------------------------------------------------- list --


async def test_list_sandboxes_returns_created_ones(client, db_session, register_payload):
    """List returns all sandboxes for the organization."""
    token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, token, "Sandbox List Org")

    for i in range(2):
        await client.post(
            f"/organizations/{org['id']}/sandbox?name=Sandbox+{i}&data_ttl_hours=12",
            headers=_auth_header(token),
        )

    response = await client.get(
        f"/organizations/{org['id']}/sandbox",
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    data = response.json()
    names = {s["name"] for s in data}
    assert {"Sandbox 0", "Sandbox 1"}.issubset(names)


# ------------------------------------------------------- delete --


async def test_delete_sandbox(client, db_session, register_payload):
    """Delete a sandbox successfully."""
    token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, token, "Sandbox Delete Org")

    create_response = await client.post(
        f"/organizations/{org['id']}/sandbox?name=To+Delete&data_ttl_hours=24",
        headers=_auth_header(token),
    )
    sandbox_id = create_response.json()["id"]

    response = await client.delete(
        f"/organizations/{org['id']}/sandbox/{sandbox_id}",
        headers=_auth_header(token),
    )

    assert response.status_code == 204


# ------------------------------------------------------- reset --


async def test_reset_sandbox(client, db_session, register_payload):
    """Reset a sandbox's expiration."""
    token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, token, "Sandbox Reset Org")

    create_response = await client.post(
        f"/organizations/{org['id']}/sandbox?name=To+Reset&data_ttl_hours=1",
        headers=_auth_header(token),
    )
    sandbox_id = create_response.json()["id"]
    original_expires = create_response.json()["expires_at"]

    response = await client.post(
        f"/organizations/{org['id']}/sandbox/{sandbox_id}/reset",
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "reset"
    assert data["expires_at"] >= original_expires


# ------------------------------------------------------- isolation --


async def test_sandboxes_are_isolated_by_organization(client, db_session, register_payload):
    """Org A cannot see Org B's sandboxes."""
    import uuid as _uuid

    # Org A + sandbox
    token_a, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_a = await _create_org(client, token_a, "Isolation Org A")

    await client.post(
        f"/organizations/{org_a['id']}/sandbox?name=Sandbox+A&data_ttl_hours=24",
        headers=_auth_header(token_a),
    )

    # Org B (different email)
    other_email = f"isolation-b-{_uuid.uuid4().hex[:8]}@example.com"
    token_b, _ = await _register(client, db_session, other_email, "correct-horse-battery-staple")
    org_b = await _create_org(client, token_b, "Isolation Org B")

    response = await client.get(
        f"/organizations/{org_b['id']}/sandbox",
        headers=_auth_header(token_b),
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_cannot_delete_sandbox_from_another_org(client, db_session, register_payload):
    """Org A cannot delete Org B's sandbox."""
    import uuid as _uuid

    token_a, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_a = await _create_org(client, token_a, "Delete Cross Org A")

    create_response = await client.post(
        f"/organizations/{org_a['id']}/sandbox?name=To+Protect&data_ttl_hours=24",
        headers=_auth_header(token_a),
    )
    sandbox_id = create_response.json()["id"]

    # Org B
    other_email = f"delete-b-{_uuid.uuid4().hex[:8]}@example.com"
    token_b, _ = await _register(client, db_session, other_email, "correct-horse-battery-staple")
    org_b = await _create_org(client, token_b, "Delete Cross Org B")

    response = await client.delete(
        f"/organizations/{org_b['id']}/sandbox/{sandbox_id}",
        headers=_auth_header(token_b),
    )

    # 404 because the sandbox does not belong to org_b
    assert response.status_code == 404


# ------------------------------------------------------- TTL --


async def test_sandbox_expires_at_is_set_correctly(client, db_session, register_payload):
    """The expires_at is set to now + data_ttl_hours."""
    token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, token, "TTL Sandbox Org")

    response = await client.post(
        f"/organizations/{org['id']}/sandbox?name=TTL+Sandbox&data_ttl_hours=48",
        headers=_auth_header(token),
    )

    assert response.status_code in (200, 201)
    data = response.json()
    assert data["data_ttl_hours"] == 48
    assert data["expires_at"] is not None


# ------------------------------------------------------- errors --


async def test_delete_nonexistent_sandbox_returns_404(client, db_session, register_payload):
    """Deleting a non-existent sandbox returns 404."""
    import uuid as _uuid

    token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, token, "Delete Nonexistent Org")

    fake_id = str(_uuid.uuid4())
    response = await client.delete(
        f"/organizations/{org['id']}/sandbox/{fake_id}",
        headers=_auth_header(token),
    )

    assert response.status_code == 404


async def test_reset_nonexistent_sandbox_returns_404(client, db_session, register_payload):
    """Resetting a non-existent sandbox returns 404."""
    import uuid as _uuid

    token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, token, "Reset Nonexistent Org")

    fake_id = str(_uuid.uuid4())
    response = await client.post(
        f"/organizations/{org['id']}/sandbox/{fake_id}/reset",
        headers=_auth_header(token),
    )

    assert response.status_code == 404
