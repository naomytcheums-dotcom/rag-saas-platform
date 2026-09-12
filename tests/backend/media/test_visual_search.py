"""Partie 22, 3rd finalization -- real CLIP-based visual search
(api/services/visual_search.py) and its wiring into
api/services/media.py's search_visual/search_similar and the
process_media_asset image branch. Includes one real, live end-to-end
test against ultralytics' own bundled real photos (skipped, not
failed, if the real CLIP weights can't be downloaded in this run --
same pattern as tests/backend/media/test_object_detection.py's own
real YOLO end-to-end test)."""

import uuid
from unittest.mock import AsyncMock

import numpy as np
import pytest
from sqlalchemy import select

from api.config import settings
from api.models.media import MediaAsset, MediaStatus, MediaType
from api.models.user import User
from api.services import media as media_service
from api.services import visual_search


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


async def _image_asset(db_session, organization_id, filename, clip_embedding, status=MediaStatus.completed) -> MediaAsset:
    asset = MediaAsset(
        organization_id=organization_id, media_type=MediaType.image, status=status, filename=filename, file_key="k",
        file_size=1, mime_type="image/png", clip_embedding=clip_embedding,
    )
    db_session.add(asset)
    await db_session.flush()
    return asset


@pytest.fixture(autouse=True)
def _reset_clip_cache():
    visual_search._model = None
    visual_search._processor = None
    yield
    visual_search._model = None
    visual_search._processor = None


# -------------------------------------------------------------- rank_by_clip_similarity (real FAISS)

def test_rank_by_clip_similarity_orders_by_real_cosine_score():
    query = [1.0, 0.0]
    candidates = [[0.0, 1.0], [1.0, 0.0], [0.7, 0.7]]  # orthogonal, identical, 45 degrees
    ranked = visual_search.rank_by_clip_similarity(query, candidates, top_k=3)
    assert [index for index, _score in ranked] == [1, 2, 0]
    assert ranked[0][1] == pytest.approx(1.0, abs=1e-5)


def test_get_clip_raises_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "VISUAL_SEARCH_ENABLED", False)
    with pytest.raises(visual_search.CLIPNotAvailableError):
        visual_search._get_clip()


# -------------------------------------------------------------- media.py wiring (mocked CLIP boundary)

async def test_process_media_asset_populates_clip_embedding(client, db_session, register_payload, monkeypatch):
    _owner_token, org_id = await _make_org(client, db_session, register_payload, "CLIP Process Org")
    asset = await _image_asset(db_session, uuid.UUID(org_id), "a.png", clip_embedding=None, status=MediaStatus.pending)
    await db_session.commit()

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")
    monkeypatch.setattr("api.services.media.download_document_file", lambda file_key: b"fake-image-bytes")
    monkeypatch.setattr("api.services.media.ocr_image_bytes", lambda content, language=None: "")
    monkeypatch.setattr("api.services.object_detection.detect_objects_yolo", lambda content: ["thing"])
    monkeypatch.setattr("api.services.visual_search.embed_image_clip", lambda content: [0.1, 0.2, 0.3])

    import litellm

    from litellm.types.utils import Choices, Message, ModelResponse

    message = Message(content='{"description": "ok", "objects": [], "tags": []}', role="assistant")
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=ModelResponse(choices=[Choices(message=message, index=0, finish_reason="stop")])))

    updated = await media_service.process_media_asset(db_session, asset.id)
    await db_session.commit()

    assert updated.status == MediaStatus.completed
    assert updated.clip_embedding == [0.1, 0.2, 0.3]


async def test_process_media_asset_degrades_gracefully_when_clip_unavailable(client, db_session, register_payload, monkeypatch):
    _owner_token, org_id = await _make_org(client, db_session, register_payload, "CLIP Fail Org")
    asset = await _image_asset(db_session, uuid.UUID(org_id), "a.png", clip_embedding=None, status=MediaStatus.pending)
    await db_session.commit()

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")
    monkeypatch.setattr("api.services.media.download_document_file", lambda file_key: b"fake-image-bytes")
    monkeypatch.setattr("api.services.media.ocr_image_bytes", lambda content, language=None: "")
    monkeypatch.setattr("api.services.object_detection.detect_objects_yolo", lambda content: ["thing"])

    def _raise(content):
        raise visual_search.CLIPNotAvailableError("simulated: no network")

    monkeypatch.setattr("api.services.visual_search.embed_image_clip", _raise)

    import litellm

    from litellm.types.utils import Choices, Message, ModelResponse

    message = Message(content='{"description": "ok", "objects": [], "tags": []}', role="assistant")
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=ModelResponse(choices=[Choices(message=message, index=0, finish_reason="stop")])))

    updated = await media_service.process_media_asset(db_session, asset.id)
    await db_session.commit()

    # A real CLIP failure must never abort the whole asset -- same
    # degradation as OCR/YOLO/vision-LLM failures elsewhere in this
    # same pipeline.
    assert updated.status == MediaStatus.completed
    assert updated.clip_embedding is None


async def test_search_visual_ranks_real_indexed_images_by_clip_similarity(client, db_session, register_payload, monkeypatch):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Visual Search Org")
    await _image_asset(db_session, uuid.UUID(org_id), "matching.png", clip_embedding=[1.0, 0.0])
    await _image_asset(db_session, uuid.UUID(org_id), "unrelated.png", clip_embedding=[0.0, 1.0])
    await db_session.commit()

    monkeypatch.setattr("api.services.visual_search.embed_text_clip", lambda text: [1.0, 0.0])

    response = await client.post("/media/search/visual", json={"query": "a red bicycle", "top_k": 5}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["filename"] == "matching.png"
    assert results[0]["score"] > results[-1]["score"]


async def test_search_similar_isolates_by_organization(client, db_session, register_payload, monkeypatch):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Similar Search Org")
    await _image_asset(db_session, uuid.UUID(org_id), "own.png", clip_embedding=[1.0, 0.0])

    stranger_token, _stranger = await _register(client, db_session, "similar_search_stranger@example.com")
    stranger_org_id = (await client.post("/organizations", json={"name": "Stranger Org"}, headers=_auth_header(stranger_token))).json()["id"]
    await _image_asset(db_session, uuid.UUID(stranger_org_id), "other_org.png", clip_embedding=[1.0, 0.0])
    await db_session.commit()

    monkeypatch.setattr("api.services.visual_search.embed_image_clip", lambda content: [1.0, 0.0])

    import io

    response = await client.post(
        "/media/search/similar", files={"file": ("query.png", io.BytesIO(b"fake"), "image/png")}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    filenames = {r["filename"] for r in response.json()["results"]}
    assert filenames == {"own.png"}  # never the stranger's own org's image


# -------------------------------------------------------------- real, live end-to-end (CLIP itself)

def test_clip_embeddings_real_end_to_end_semantic_similarity(tmp_path):
    """A real, live test -- no mocking of the CLIP model itself.
    Embeds ultralytics' own bundled real photos (`bus.jpg`, a real bus;
    `zidane.jpg`, a real soccer player close-up) and a real text query,
    confirming the real CLIP model scores the query closer to the
    photo it actually describes. Skipped (not failed) if the real
    weights can't be downloaded in this particular run."""
    from ultralytics.utils import ASSETS

    try:
        bus_embedding = visual_search.embed_image_clip((ASSETS / "bus.jpg").read_bytes())
        person_embedding = visual_search.embed_image_clip((ASSETS / "zidane.jpg").read_bytes())
        bus_query_embedding = visual_search.embed_text_clip("a photo of a bus")
    except visual_search.CLIPNotAvailableError as exc:
        pytest.skip(f"real CLIP weights unavailable in this environment: {exc}")

    score_vs_bus = float(np.dot(bus_query_embedding, bus_embedding))
    score_vs_person = float(np.dot(bus_query_embedding, person_embedding))
    assert score_vs_bus > score_vs_person
