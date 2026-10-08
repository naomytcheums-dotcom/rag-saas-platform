"""Endpoints that an anonymous sweep found open (tests/test_no_unhandled_errors_sweep.py): the document reindex trigger and /metrics."""

import uuid

from api.config import settings


async def test_reindex_sync_refuses_an_anonymous_caller_and_never_starts_a_task(client, monkeypatch):
    started = []
    monkeypatch.setattr("api.routers.documents_sync._run_reindex_safe", lambda document_id: started.append(document_id))
    response = await client.post(f"/documents/{uuid.uuid4()}/reindex-sync")
    assert response.status_code in (401, 403)
    assert started == []


async def test_reindex_sync_for_a_document_the_caller_cannot_see_is_a_404_and_starts_nothing(client, register_payload, monkeypatch):
    started = []
    monkeypatch.setattr("api.routers.documents_sync._run_reindex_safe", lambda document_id: started.append(document_id))
    token = (await client.post("/auth/register", json={"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True})).json()["access_token"]
    response = await client.post(f"/documents/{uuid.uuid4()}/reindex-sync", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404
    assert started == []


async def test_metrics_stays_open_when_no_token_is_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_AUTH_TOKEN", None)
    assert (await client.get("/metrics")).status_code == 200


async def test_metrics_requires_the_bearer_token_when_one_is_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_AUTH_TOKEN", "scrape-token-value")
    assert (await client.get("/metrics")).status_code == 401
    assert (await client.get("/metrics", headers={"Authorization": "Bearer wrong"})).status_code == 401
    assert (await client.get("/metrics", headers={"Authorization": "Basic scrape-token-value"})).status_code == 401
    ok = await client.get("/metrics", headers={"Authorization": "Bearer scrape-token-value"})
    assert ok.status_code == 200
