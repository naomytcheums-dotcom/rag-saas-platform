"""Partie 15.1/15.2 -- IntegrationConnection CRUD lifecycle: create
(token shown once), get/list, update, delete, the dry-run test
endpoint, and the static provider catalog."""


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register_and_create_org(client, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Integrations Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id


async def test_list_providers_returns_the_static_catalog(client):
    response = await client.get("/integrations/providers")
    assert response.status_code == 200
    ids = {p["id"] for p in response.json()}
    assert ids == {"webhook", "zapier", "make", "n8n"}


async def test_create_connection_returns_token_once(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.post(f"/organizations/{org_id}/integrations/connections", json={"name": "n8n webhook", "provider": "n8n", "action": "log_only"}, headers=_auth_header(token))
    assert response.status_code == 201
    assert len(response.json()["token"]) > 20


async def test_list_connections_returns_created_connection(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    await client.post(f"/organizations/{org_id}/integrations/connections", json={"name": "n8n webhook", "provider": "n8n"}, headers=_auth_header(token))

    response = await client.get(f"/organizations/{org_id}/integrations/connections", headers=_auth_header(token))
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_get_single_connection(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(f"/organizations/{org_id}/integrations/connections", json={"name": "n8n webhook", "provider": "n8n"}, headers=_auth_header(token))
    connection_id = created.json()["id"]

    response = await client.get(f"/organizations/{org_id}/integrations/connections/{connection_id}", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["name"] == "n8n webhook"


async def test_get_single_connection_404_for_unknown_id(client, register_payload):
    import uuid

    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.get(f"/organizations/{org_id}/integrations/connections/{uuid.uuid4()}", headers=_auth_header(token))
    assert response.status_code == 404


async def test_update_connection_name_and_active_flag(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(f"/organizations/{org_id}/integrations/connections", json={"name": "old-name", "provider": "webhook"}, headers=_auth_header(token))
    connection_id = created.json()["id"]

    response = await client.patch(f"/organizations/{org_id}/integrations/connections/{connection_id}", json={"name": "new-name", "is_active": False}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["name"] == "new-name"
    assert response.json()["is_active"] is False


async def test_delete_connection(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(f"/organizations/{org_id}/integrations/connections", json={"name": "temp", "provider": "webhook"}, headers=_auth_header(token))
    connection_id = created.json()["id"]

    delete_response = await client.delete(f"/organizations/{org_id}/integrations/connections/{connection_id}", headers=_auth_header(token))
    assert delete_response.status_code == 204

    get_response = await client.get(f"/organizations/{org_id}/integrations/connections/{connection_id}", headers=_auth_header(token))
    assert get_response.status_code == 404


async def test_connection_dry_run_never_persists_a_real_document(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(f"/organizations/{org_id}/integrations/connections", json={"name": "crm-ingest", "provider": "webhook", "action": "ingest_document"}, headers=_auth_header(token))
    connection_id = created.json()["id"]

    response = await client.post(f"/organizations/{org_id}/integrations/connections/{connection_id}/test", headers=_auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body["would_run_action"] == "ingest_document"
    assert body["connection_active"] is True

    documents = await client.get(f"/organizations/{org_id}/documents", headers=_auth_header(token))
    assert documents.json()["items"] == []
