"""An organization cannot select an embedding model this pipeline cannot load: the hosted OpenAI / Cohere models used to be accepted (200) and only showed up
later as documents ending in `failed` (found by scripts/e2e_rag_ingestion_search.py on a real stack)."""

import uuid

import pytest


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _owner_with_org(client, register_payload):
    token = (await client.post("/auth/register", json={"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True})).json()["access_token"]
    org = (await client.post("/organizations", json={"name": f"Embed {uuid.uuid4().hex[:6]}"}, headers=_auth(token))).json()
    return token, org["id"]


@pytest.mark.parametrize("model", ["openai/text-embedding-ada-002", "cohere/embed-english-v3.0"])
async def test_a_hosted_embedding_model_the_pipeline_cannot_load_is_refused_with_a_clear_error(client, register_payload, model):
    token, org_id = await _owner_with_org(client, register_payload)

    response = await client.patch(f"/organizations/{org_id}/settings", json={"embedding_model": model}, headers=_auth(token))

    assert response.status_code == 422
    assert "not available" in response.text and model in response.text
    stored = (await client.get(f"/organizations/{org_id}/settings", headers=_auth(token))).json()["embedding_model"]
    assert stored == "sentence-transformers/all-MiniLM-L6-v2"


@pytest.mark.parametrize("model", ["sentence-transformers/all-mpnet-base-v2", "BAAI/bge-small-en-v1.5"])
async def test_local_models_stay_accepted_including_ones_the_catalogue_does_not_list(client, register_payload, model):
    token, org_id = await _owner_with_org(client, register_payload)

    response = await client.patch(f"/organizations/{org_id}/settings", json={"embedding_model": model}, headers=_auth(token))

    assert response.status_code == 200, response.text
    assert response.json()["embedding_model"] == model
