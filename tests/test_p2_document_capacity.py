"""Specs 1.3.6 / 12.3.2 / 12.3.3 -- document count and storage limits on the batch upload, the importers and the single upload. Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.models.document import Document
from api.models.organization_quota import OrganizationQuota


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _org(client, email):
    token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    org = (await client.post("/organizations", json={"name": f"Org {email}"}, headers=_h(token))).json()
    return token, uuid.UUID(org["id"])


async def _fill(db_session, org_id, n, size=1):
    for i in range(n):
        db_session.add(Document(organization_id=org_id, name=f"d{i}.txt", file_type="txt", file_size=size, status="ready", file_key=f"k/{uuid.uuid4()}"))
    await db_session.commit()


async def _set_plan_limit(db_session, org_id, limit):
    from api.models.admin import Plan, Subscription

    plan = Plan(key=f"p{uuid.uuid4().hex[:6]}", name="Tiny", monthly_price_cents=0, yearly_price_cents=0, max_documents=limit)
    db_session.add(plan)
    await db_session.flush()
    existing = await db_session.scalar(select(Subscription).where(Subscription.organization_id == org_id))
    if existing is not None:
        existing.plan_id = plan.id
    else:
        db_session.add(Subscription(organization_id=org_id, plan_id=plan.id, status="active"))
    await db_session.commit()


async def test_importers_are_refused_when_the_plan_document_limit_is_reached(client, db_session):
    token, org_id = await _org(client, "cap-import@example.com")
    await _set_plan_limit(db_session, org_id, 2)
    await _fill(db_session, org_id, 2)
    for path, body in (("url", {"url": "https://example.com/a"}), ("sitemap", {"url": "https://example.com/sitemap.xml"}), ("notion", {"page_id": "x", "token": "t"})):
        r = await client.post(f"/organizations/{org_id}/documents/{path}", json=body, headers=_h(token))
        assert r.status_code == 402, (path, r.status_code, r.text[:200])
        assert "plan allows 2 documents" in r.json()["detail"]


async def test_batch_upload_must_fit_entirely(client, db_session):
    token, org_id = await _org(client, "cap-batch@example.com")
    await _set_plan_limit(db_session, org_id, 3)
    await _fill(db_session, org_id, 2)
    files = [("files", (f"f{i}.txt", b"hello world", "text/plain")) for i in range(3)]
    r = await client.post(f"/organizations/{org_id}/documents/batch", files=files, headers=_h(token))
    assert r.status_code == 402 and "would exceed" in r.json()["detail"]


async def test_storage_quota_blocks_an_upload_that_does_not_fit(client, db_session):
    token, org_id = await _org(client, "cap-storage@example.com")
    quota = await db_session.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == org_id))
    quota.max_storage_mb = 1
    await db_session.commit()
    await _fill(db_session, org_id, 1, size=1024 * 1024 - 10)
    r = await client.post(f"/organizations/{org_id}/documents", files={"file": ("big.txt", b"x" * 100, "text/plain")}, headers=_h(token))
    assert r.status_code == 402 and "Storage quota exceeded" in r.json()["detail"]
    batch = await client.post(f"/organizations/{org_id}/documents/batch", files=[("files", ("b.txt", b"x" * 100, "text/plain"))], headers=_h(token))
    assert batch.status_code == 402


async def test_a_non_member_learns_nothing_about_the_plan(client, db_session):
    _token, org_id = await _org(client, "cap-owner@example.com")
    await _set_plan_limit(db_session, org_id, 1)
    await _fill(db_session, org_id, 1)
    stranger, _ = await _org(client, "cap-stranger@example.com")
    r = await client.post(f"/organizations/{org_id}/documents/url", json={"url": "https://example.com/a"}, headers=_h(stranger))
    assert r.status_code in (403, 404) and "plan" not in r.text
