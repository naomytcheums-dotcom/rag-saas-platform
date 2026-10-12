"""E2E finding 2026-10-12: a missing S3 setting was an unhandled OSError (HTTP 500)."""

from api.config import settings


async def test_upload_without_storage_settings_is_a_503_that_names_the_variables(client, register_payload, monkeypatch):
    token = (await client.post("/auth/register", json={**register_payload, "accept_terms": True})).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    org = (await client.post("/organizations", json={"name": "Acme"}, headers=headers)).json()
    monkeypatch.setattr(settings, "S3_DOCUMENTS_BUCKET_NAME", None)

    response = await client.post(f"/organizations/{org['id']}/documents", headers=headers, files={"file": ("a.txt", b"hello world, a real note", "text/plain")})

    assert response.status_code == 503
    assert "S3_DOCUMENTS_BUCKET_NAME" in response.json()["detail"]
