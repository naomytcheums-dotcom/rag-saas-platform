"""Spec 6.1.8 -- GET /citations/{id}/preview."""

import uuid

from sqlalchemy import select

from api.models.citation import Citation
from api.models.response import Response
from api.models.user import User


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _citation(client, db_session, email, text):
    token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    org = (await client.post("/organizations", json={"name": "Preview Org"}, headers=_h(token))).json()
    response = Response(organization_id=uuid.UUID(org["id"]), query="q", answer="a", created_by=user.id)
    db_session.add(response)
    await db_session.flush()
    citation = Citation(response_id=response.id, text=text, relevance_score=0.9, citation_number=1)
    db_session.add(citation)
    await db_session.commit()
    return token, citation.id


async def test_preview_returns_a_short_prefix_of_the_cited_passage(client, db_session):
    token, cid = await _citation(client, db_session, "prev-owner@example.com", "word " * 400)
    body = (await client.get(f"/citations/{cid}/preview", headers=_h(token))).json()
    assert body["citation_id"] == str(cid)
    assert 0 < len(body["preview"]) < 400
    short = (await client.get(f"/citations/{cid}/preview?preview_length=20", headers=_h(token))).json()["preview"]
    assert len(short) <= 30


async def test_preview_follows_the_citation_access_rule(client, db_session):
    _token, cid = await _citation(client, db_session, "prev-a@example.com", "secret passage of tenant A")
    other = (await client.post("/auth/register", json={"email": "prev-b@example.com", "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    assert (await client.get(f"/citations/{cid}/preview", headers=_h(other))).status_code in (403, 404)
    assert (await client.get(f"/citations/{uuid.uuid4()}/preview", headers=_h(other))).status_code in (403, 404)
