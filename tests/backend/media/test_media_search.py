"""Partie 22 -- real search over media-derived text, reusing
`api.security.documents.generate_embeddings` (real sentence-transformers
model, already loaded for the rest of this test suite -- no mocking
needed, unlike the LLM/OCR/ffmpeg boundaries the other Partie 22 test
files mock) and `api.services.retrieval_pipeline.cosine_similarities`."""

import uuid

from sqlalchemy import select

from api.models.document import DocumentChunk
from api.models.media import MediaAsset, MediaStatus, MediaType
from api.models.user import User
from api.security.documents import generate_embeddings
from api.services import media as media_service


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org(client, db_session, register_payload, name):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    return owner_token, org_id


async def _index_one_asset(db_session, organization_id: uuid.UUID, media_type: MediaType, text: str, source: str) -> MediaAsset:
    asset = MediaAsset(
        organization_id=organization_id, media_type=media_type, status=MediaStatus.completed, filename="a", file_key="k",
        file_size=1, mime_type="image/png",
    )
    db_session.add(asset)
    await db_session.flush()
    [embedding] = generate_embeddings([text], "sentence-transformers/all-MiniLM-L6-v2")
    db_session.add(DocumentChunk(
        document_id=None, media_asset_id=asset.id, organization_id=organization_id, content=text,
        metadata_json={"source": source, "media_type": media_type.value}, embedding=embedding, chunk_index=1,
    ))
    await db_session.commit()
    return asset


async def test_search_media_finds_the_real_matching_transcript(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Search Org")
    await _index_one_asset(db_session, uuid.UUID(org_id), MediaType.audio, "Le chat mange une souris dans le jardin.", "media_transcript")
    await _index_one_asset(db_session, uuid.UUID(org_id), MediaType.image, "Une voiture rouge garee devant un immeuble.", "media_image_description")

    response = await client.post("/media/search", json={"query": "un chat et une souris", "top_k": 5}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    results = response.json()["results"]
    assert results
    assert results[0]["source"] == "media_transcript"


async def test_search_media_respects_media_type_filter(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Filter Org")
    await _index_one_asset(db_session, uuid.UUID(org_id), MediaType.audio, "Une conversation sur la meteo.", "media_transcript")
    await _index_one_asset(db_session, uuid.UUID(org_id), MediaType.image, "Une conversation sur la meteo, en image.", "media_image_description")

    response = await client.post("/media/search", json={"query": "meteo", "media_type": "image", "top_k": 5}, headers=_auth_header(owner_token))
    results = response.json()["results"]
    assert results
    assert all(r["media_type"] == "image" for r in results)


async def test_search_media_never_returns_another_organizations_results(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Isolated Org")
    await _index_one_asset(db_session, uuid.UUID(org_id), MediaType.audio, "Un contenu strictement prive a cette organisation.", "media_transcript")

    stranger_token, _stranger = await _register(client, db_session, "media_search_stranger@example.com")
    response = await client.post("/media/search", json={"query": "contenu prive", "top_k": 5}, headers=_auth_header(stranger_token))
    assert response.json()["results"] == []
