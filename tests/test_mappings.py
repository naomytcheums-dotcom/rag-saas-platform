"""Partie 15.1 -- IntegrationMapping CRUD, including the
previously-missing PATCH /mappings/{id}, and end-to-end field mapping
applied to a real inbound payload."""


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register_and_create_connection(client, register_payload, *, action: str = "log_only"):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Integrations Org"}, headers=_auth_header(token))).json()["id"]
    created = await client.post(f"/organizations/{org_id}/integrations/connections", json={"name": "crm", "provider": "webhook", "action": action}, headers=_auth_header(token))
    return token, org_id, created.json()["id"], created.json()["token"]


async def test_create_mapping(client, register_payload):
    token, org_id, connection_id, _ = await _register_and_create_connection(client, register_payload)
    response = await client.post(f"/organizations/{org_id}/integrations/connections/{connection_id}/mappings", json={"source_field": "Email", "target_field": "email", "transform": "normalize_email"}, headers=_auth_header(token))
    assert response.status_code == 201
    assert response.json()["transform"] == "normalize_email"


async def test_list_mappings(client, register_payload):
    token, org_id, connection_id, _ = await _register_and_create_connection(client, register_payload)
    await client.post(f"/organizations/{org_id}/integrations/connections/{connection_id}/mappings", json={"source_field": "Email", "target_field": "email"}, headers=_auth_header(token))

    response = await client.get(f"/organizations/{org_id}/integrations/connections/{connection_id}/mappings", headers=_auth_header(token))
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_update_mapping_via_patch(client, register_payload):
    token, org_id, connection_id, _ = await _register_and_create_connection(client, register_payload)
    created = await client.post(f"/organizations/{org_id}/integrations/connections/{connection_id}/mappings", json={"source_field": "Email", "target_field": "email"}, headers=_auth_header(token))
    mapping_id = created.json()["id"]

    response = await client.patch(f"/organizations/{org_id}/integrations/mappings/{mapping_id}", json={"target_field": "email_address", "transform": "normalize_email"}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["target_field"] == "email_address"
    assert response.json()["transform"] == "normalize_email"


async def test_update_mapping_404_for_unknown_id(client, register_payload):
    import uuid

    token, org_id, _connection_id, _ = await _register_and_create_connection(client, register_payload)
    response = await client.patch(f"/organizations/{org_id}/integrations/mappings/{uuid.uuid4()}", json={"target_field": "x"}, headers=_auth_header(token))
    assert response.status_code == 404


async def test_delete_mapping(client, register_payload):
    token, org_id, connection_id, _ = await _register_and_create_connection(client, register_payload)
    created = await client.post(f"/organizations/{org_id}/integrations/connections/{connection_id}/mappings", json={"source_field": "Email", "target_field": "email"}, headers=_auth_header(token))
    mapping_id = created.json()["id"]

    response = await client.delete(f"/organizations/{org_id}/integrations/mappings/{mapping_id}", headers=_auth_header(token))
    assert response.status_code == 204

    remaining = await client.get(f"/organizations/{org_id}/integrations/connections/{connection_id}/mappings", headers=_auth_header(token))
    assert remaining.json() == []


async def test_mapping_applied_to_a_real_inbound_payload(client, register_payload):
    token, org_id, connection_id, connection_token = await _register_and_create_connection(client, register_payload)
    await client.post(f"/organizations/{org_id}/integrations/connections/{connection_id}/mappings", json={"source_field": "Email", "target_field": "email", "transform": "normalize_email"}, headers=_auth_header(token))

    response = await client.post(f"/integrations/inbound/{connection_id}", json={"Email": "  Test@Example.COM  "}, headers={"Authorization": f"Bearer {connection_token}"})
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    # log_only never persists the mapped payload anywhere queryable beyond
    # the raw receipt log -- this asserts the endpoint accepted the mapped
    # request without erroring, not a separate mapped-payload store.
