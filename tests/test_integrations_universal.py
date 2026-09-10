"""Partie 15 -- universal inbound integrations (connection CRUD, real
bearer-token auth, real field mapping/transform, real document
ingestion action) and Airbyte's honest 501-when-unconfigured."""

import uuid


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register_and_create_org(client, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Integrations Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id


async def test_create_connection_returns_token_once(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.post(f"/organizations/{org_id}/integrations/connections", json={"name": "n8n webhook", "provider": "n8n", "action": "log_only"}, headers=_auth_header(token))
    assert response.status_code == 201
    assert len(response.json()["token"]) > 20


async def test_inbound_webhook_rejects_wrong_token(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(f"/organizations/{org_id}/integrations/connections", json={"name": "zapier", "provider": "zapier"}, headers=_auth_header(token))
    connection_id = created.json()["id"]

    response = await client.post(f"/integrations/inbound/{connection_id}", json={"foo": "bar"}, headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 401


async def test_inbound_webhook_accepted_with_real_token_log_only(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(f"/organizations/{org_id}/integrations/connections", json={"name": "zapier", "provider": "zapier", "action": "log_only"}, headers=_auth_header(token))
    connection_id, connection_token = created.json()["id"], created.json()["token"]

    response = await client.post(f"/integrations/inbound/{connection_id}", json={"email": "Test@Example.COM"}, headers={"Authorization": f"Bearer {connection_token}"})
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

    logs = await client.get(f"/organizations/{org_id}/integrations/connections/{connection_id}/logs", headers=_auth_header(token))
    assert len(logs.json()) == 1


async def test_field_mapping_normalizes_email(client, db_session, register_payload):
    from api.services.integrations import apply_mapping
    from api.models.integrations import IntegrationMapping

    mapping = IntegrationMapping(connection_id=uuid.uuid4(), source_field="Email", target_field="email", transform="normalize_email")
    result = apply_mapping({"Email": "  Test@Example.COM  "}, [mapping])
    assert result == {"email": "test@example.com"}


async def test_ingest_document_action_creates_a_real_document(client, register_payload):
    import pytest

    from api.config import settings

    if not settings.S3_DOCUMENTS_BUCKET_NAME:
        pytest.skip("S3_DOCUMENTS_BUCKET_NAME is not configured -- skipping the real end-to-end document pipeline test")

    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(f"/organizations/{org_id}/integrations/connections", json={"name": "crm-ingest", "provider": "webhook", "action": "ingest_document"}, headers=_auth_header(token))
    connection_id, connection_token = created.json()["id"], created.json()["token"]

    response = await client.post(f"/integrations/inbound/{connection_id}", json={"title": "New lead", "notes": "Interested in enterprise plan"}, headers={"Authorization": f"Bearer {connection_token}"})
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

    documents = await client.get(f"/organizations/{org_id}/documents", headers=_auth_header(token))
    assert documents.status_code == 200
    assert len(documents.json()["items"]) == 1


async def test_delete_connection_invalidates_inbound_token(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(f"/organizations/{org_id}/integrations/connections", json={"name": "temp", "provider": "webhook"}, headers=_auth_header(token))
    connection_id, connection_token = created.json()["id"], created.json()["token"]

    delete_response = await client.delete(f"/organizations/{org_id}/integrations/connections/{connection_id}", headers=_auth_header(token))
    assert delete_response.status_code == 204

    response = await client.post(f"/integrations/inbound/{connection_id}", json={}, headers={"Authorization": f"Bearer {connection_token}"})
    assert response.status_code == 401


async def test_airbyte_honestly_501s_without_configured_instance(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.get(f"/organizations/{org_id}/integrations/airbyte/source-definitions", headers=_auth_header(token))
    assert response.status_code == 501


async def test_n8n_status_honestly_unconfigured_by_default(client):
    response = await client.get("/integrations/n8n/status")
    assert response.status_code == 200
    assert response.json() == {"configured": False, "reachable": False}


async def test_airbyte_status_honestly_unconfigured_by_default(client):
    response = await client.get("/integrations/airbyte/status")
    assert response.status_code == 200
    assert response.json() == {"configured": False, "reachable": False}
