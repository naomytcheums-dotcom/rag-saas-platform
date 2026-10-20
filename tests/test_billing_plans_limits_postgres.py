"""Billing, plan limits, credits and agent deployment -- the REAL FastAPI application against a REAL PostgreSQL (no SQLite, no dependency override).

What is real here: the HTTP application (ASGI), PostgreSQL (row locks, advisory locks, ON CONFLICT upserts, Row Level Security tables), the plan catalogue seeded
by the application, the document upload route and its S3 storage (local MinIO), the orchestrator's credit and question pre-flights, the Stripe webhook
signature check done by the real `stripe` SDK, the Paystack HMAC check.

What is NOT real, and is said so: the LLM (`litellm.acompletion` is replaced by a local fake that returns a fixed answer with a fixed token usage, so that the
credit arithmetic is exact and no paid provider is called) and the payment providers (Stripe and Paystack events are produced by this file with the
providers' documented signing schemes -- Stripe `t=...,v1=HMAC-SHA256`, Paystack `HMAC-SHA512` -- and posted to our own webhook routes; no money moves and
no vendor account is involved). A green run here proves OUR handling of such events, not the vendors' behaviour: the real sandbox validation is a separate,
owner-run step (see docs/project-handover/e2e_evidence/billing_RESUME.md).

Runs only against a local PostgreSQL whose database name contains "test" (it creates users, organizations and documents); skipped otherwise:

    source scripts/test_env/e2e_stack_env.sh   # or any environment pointing DATABASE_URL at a local *test* database already migrated
    python -m pytest tests/test_billing_plans_limits_postgres.py -p no:cacheprovider
"""

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from unittest.mock import AsyncMock, patch

import litellm
import pytest
from httpx import ASGITransport, AsyncClient
from litellm.types.utils import Choices, Message, ModelResponse, Usage
from sqlalchemy import func, select, update

from api.config import settings
from api.database import AsyncSessionLocal
from api.main import app
from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.billing import Credit, CreditTransaction, CreditTransactionType, PaymentEvent
from api.models.document import Document
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.organization_usage import OrganizationUsage

_url = str(settings.DATABASE_URL)
_LOCAL_TEST_PG = _url.startswith("postgresql") and ("127.0.0.1" in _url or "localhost" in _url) and "test" in _url.rsplit("/", 1)[-1]
pytestmark = pytest.mark.skipif(not _LOCAL_TEST_PG, reason="needs DATABASE_URL on a local PostgreSQL database whose name contains 'test'")

PASSWORD = "Correct-Horse-Battery-Staple-9!"
CALL_COST = 5  # 500 prompt tokens / 100 tokens per credit (see api/security/credit_packs.py)


# ----------------------------------------------------------------------------------------------------------------- fixtures / helpers


@pytest.fixture
async def client():
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()  # the SQLite fixtures of the other test modules must not leak in: this module talks to PostgreSQL
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=60) as c:
        yield c
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


@pytest.fixture(autouse=True)
def _fake_llm_and_keys(monkeypatch):
    """The LLM is a local fake with an exact token usage (500 prompt tokens = 5 credits)."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-local-fake")
    monkeypatch.setattr(settings, "LLM_DEFAULT_PROVIDER", "anthropic")
    monkeypatch.setattr(settings, "LLM_DEFAULT_MODEL", "claude-3-5-sonnet-20241022")
    fake = AsyncMock(return_value=ModelResponse(
        choices=[Choices(message=Message(content="A locally faked answer.", role="assistant"), index=0, finish_reason="stop")],
        usage=Usage(prompt_tokens=500, completion_tokens=0, total_tokens=500),
    ))
    monkeypatch.setattr(litellm, "acompletion", fake)
    return fake


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def new_user(client) -> dict:
    email = f"billing-{uuid.uuid4().hex[:10]}@example.com"
    with patch("api.routers.auth.create_and_send_email_otp", new=AsyncMock()):
        r = await client.post("/auth/register", json={"email": email, "password": PASSWORD, "full_name": "Billing Test", "accept_terms": True})
    assert r.status_code in (200, 201), r.text
    body = r.json()
    me = await client.get("/account/me", headers=_h(body["access_token"]))
    return {"email": email, "token": body["access_token"], "id": uuid.UUID(me.json()["id"])}


async def new_org(client, owner: dict) -> uuid.UUID:
    r = await client.post("/organizations", json={"name": f"Billing {uuid.uuid4().hex[:6]}"}, headers=_h(owner["token"]))
    assert r.status_code in (200, 201), r.text
    return uuid.UUID(r.json()["id"])


async def add_member(org_id: uuid.UUID, user: dict, role: OrganizationRole) -> None:
    async with AsyncSessionLocal() as db:
        db.add(OrganizationMember(organization_id=org_id, user_id=user["id"], role=role))
        await db.commit()


async def set_plan(org_id: uuid.UUID, key: str, *, status: SubscriptionStatus = SubscriptionStatus.active) -> Plan:
    """Assign a catalogue plan the way the provider webhook / back office does (not through the self-service route, which refuses paid plans)."""
    async with AsyncSessionLocal() as db:
        plan = await db.scalar(select(Plan).where(Plan.key == key))
        from api.services.admin_subscriptions import get_or_create_subscription

        sub = await get_or_create_subscription(db, org_id)
        assert plan is not None
        sub.plan_id, sub.status = plan.id, status
        await db.commit()
        return plan


async def seed_catalogue(client) -> dict[str, dict]:
    r = await client.get("/billing/plans")
    assert r.status_code == 200, r.text
    return {p["key"]: p for p in r.json()}


async def upload(client, owner: dict, org_id, label: str, *, expect: int | None = 201):
    body = f"Document {label} {uuid.uuid4().hex} about the quarterly maintenance schedule of the gateway.".encode()
    r = await client.post(f"/organizations/{org_id}/documents", headers=_h(owner["token"]), files={"file": (f"{label}.txt", body, "text/plain")})
    if expect is not None:
        assert r.status_code == expect, f"upload {label}: {r.status_code} {r.text[:300]}"
    return r


async def doc_count(org_id) -> int:
    async with AsyncSessionLocal() as db:
        return int(await db.scalar(select(func.count()).select_from(Document).where(Document.organization_id == org_id, Document.deleted_at.is_(None))) or 0)


async def credit_balance(org_id) -> int | None:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(Credit.balance).where(Credit.organization_id == org_id))


async def set_balance(org_id, balance: int) -> None:
    async with AsyncSessionLocal() as db:
        credit = await db.scalar(select(Credit).where(Credit.organization_id == org_id))
        if credit is None:
            db.add(Credit(organization_id=org_id, balance=balance))
        else:
            credit.balance = balance
        await db.commit()


async def deployed_agent(client, owner: dict, org_id) -> tuple[str, str]:
    """An agent created through the API plus an `execute` API key for it: the production door `POST /api/agents/run`. Returns (agent_id, api_key)."""
    r = await client.post(f"/organizations/{org_id}/agents", headers=_h(owner["token"]), json={"name": "Support agent"})
    assert r.status_code == 201, r.text
    agent_id = r.json()["id"]
    k = await client.post(f"/agents/{agent_id}/api-keys", headers=_h(owner["token"]), json={"name": "prod", "scopes": ["execute", "read"]})
    assert k.status_code in (200, 201), k.text
    return agent_id, k.json()["key"]


async def ask(client, key: str, text: str = "What is the maintenance window?"):
    return await client.post("/api/agents/run", headers={"X-API-Key": key}, json={"input": text})


async def questions_today(org_id) -> int:
    async with AsyncSessionLocal() as db:
        return int(await db.scalar(select(func.coalesce(func.sum(OrganizationUsage.value), 0)).where(OrganizationUsage.organization_id == org_id, OrganizationUsage.metric == "questions")) or 0)


def stripe_signed(event: dict, secret: str) -> tuple[bytes, dict]:
    """Stripe's documented webhook signature: `t=<ts>,v1=HMAC_SHA256(secret, "<ts>.<payload>")`. Produced here, verified by the real `stripe` SDK in the route."""
    payload = json.dumps(event).encode()
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return payload, {"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"}


def paystack_signed(event: dict, secret: str) -> tuple[bytes, dict]:
    payload = json.dumps(event).encode()
    return payload, {"x-paystack-signature": hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest(), "content-type": "application/json"}


# ================================================================================================== 12.2.x plan catalogue (data seeded by the app)


async def test_the_default_catalogue_matches_the_specified_tiers(client):
    plans = await seed_catalogue(client)
    got = {k: (p["max_documents"], p["max_questions_per_day"]) for k, p in plans.items()}
    assert got["free"] == (3, 10)  # 12.2.1
    assert got["starter"] == (100, 500)  # 12.2.2
    assert got["pro"] == (1000, None)  # 12.2.3 -- unlimited questions
    assert got["business"] == (10_000, None)  # 12.2.4
    assert got["enterprise"] == (None, None)  # 12.2.5 -- unlimited
    assert plans["free"]["monthly_price_cents"] == 0
    assert plans["enterprise"]["sla"] is True and plans["business"]["advanced_features"] is True
    # public catalogue: no auth needed, and ordered from the cheapest to the most expensive
    prices = [p["monthly_price_cents"] for p in (await client.get("/billing/plans")).json()]
    assert prices == sorted(prices)


async def test_a_new_organization_starts_on_the_free_plan_with_its_limits(client):
    plans = await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    sub = (await client.get(f"/organizations/{org}/billing/subscription", headers=_h(owner["token"]))).json()
    assert sub["plan_id"] == plans["free"]["id"] and sub["status"] == "active"


# ================================================================================================== 12.2.1 documents at the boundary (Free = 3)


async def test_free_plan_third_document_passes_fourth_is_refused_and_a_deleted_document_frees_its_slot(client):
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    ids = []
    for i in range(1, 4):  # documents 1, 2 and 3 are accepted
        ids.append((await upload(client, owner, org, f"doc{i}")).json()["id"])
    refused = await upload(client, owner, org, "doc4", expect=None)  # the 4th is refused with 402 and a message the user can act on
    assert refused.status_code == 402 and "3 documents" in refused.json()["detail"] and "Upgrade" in refused.json()["detail"]
    assert await doc_count(org) == 3  # nothing was created by the refused request

    # deleting a document (trash) frees the slot -- before the fix the trash still counted against the plan
    assert (await client.delete(f"/documents/{ids[0]}", headers=_h(owner["token"]))).status_code == 200
    assert await doc_count(org) == 2
    await upload(client, owner, org, "doc5")  # accepted again
    assert (await upload(client, owner, org, "doc6", expect=None)).status_code == 402


async def test_the_batch_upload_is_all_or_nothing_against_the_remaining_slots(client):
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    await upload(client, owner, org, "a")
    await upload(client, owner, org, "b")  # 1 slot left
    files = [("files", (f"batch{i}.txt", f"batch file {i} {uuid.uuid4().hex}".encode(), "text/plain")) for i in range(2)]
    r = await client.post(f"/organizations/{org}/documents/batch", headers=_h(owner["token"]), files=files)
    assert r.status_code == 402, r.text
    assert await doc_count(org) == 2


async def test_url_import_is_refused_at_the_limit_too(client):
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    for i in range(3):
        await upload(client, owner, org, f"u{i}")
    r = await client.post(f"/organizations/{org}/documents/url", headers=_h(owner["token"]), json={"url": "https://example.com/page"})
    assert r.status_code == 402, r.text
    assert await doc_count(org) == 3


async def test_the_public_api_upload_cannot_bypass_the_document_limit(client):
    """`POST /v1/documents` (organization API key) called upload_document directly with no plan check before this change."""
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    k = await client.post(f"/organizations/{org}/api-keys", headers=_h(owner["token"]), json={"name": "ci", "scopes": ["documents:write", "documents:read"]})
    assert k.status_code in (200, 201), k.text
    key = k.json()["key"]

    async def public_upload(i):
        return await client.post("/v1/documents", headers={"X-API-Key": key}, files={"file": (f"p{i}.txt", f"public api doc {i} {uuid.uuid4().hex}".encode(), "text/plain")})

    for i in range(3):
        assert (await public_upload(i)).status_code in (200, 201, 202)
    r = await public_upload(4)
    assert r.status_code == 402, f"{r.status_code} {r.text[:200]}"
    assert await doc_count(org) == 3


async def test_documents_of_another_organization_are_not_counted_and_not_blocked(client):
    await seed_catalogue(client)
    a, b = await new_user(client), await new_user(client)
    org_a, org_b = await new_org(client, a), await new_org(client, b)
    for i in range(3):
        await upload(client, a, org_a, f"a{i}")
    assert (await upload(client, a, org_a, "a4", expect=None)).status_code == 402
    await upload(client, b, org_b, "b1")  # org B has its own 3 slots
    assert await doc_count(org_b) == 1
    # and B cannot upload into A's organization
    r = await client.post(f"/organizations/{org_a}/documents", headers=_h(b["token"]), files={"file": ("x.txt", b"intruder document", "text/plain")})
    assert r.status_code in (403, 404)


async def test_concurrent_uploads_cannot_take_the_same_last_slot(client):
    """Six simultaneous uploads against 3 free slots: exactly 3 are accepted (advisory lock + live count), never 4."""
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    results = await asyncio.gather(*[upload(client, owner, org, f"race{i}", expect=None) for i in range(6)])
    codes = sorted(r.status_code for r in results)
    assert codes.count(201) == 3 and codes.count(402) == 3, codes
    assert await doc_count(org) == 3


@pytest.mark.parametrize("plan_key,limit", [("starter", 100), ("pro", 1000), ("business", 10_000)])
async def test_paid_plans_carry_their_document_limit_and_enterprise_has_none(client, plan_key, limit):
    """Boundary of each paid tier, checked on the live count with the real service (uploading 100 / 1000 / 10 000 files through S3 would only prove the loop):
    at limit-1 documents one more fits, at limit it does not. Enterprise has no cap."""
    from api.services.billing_usage import DocumentLimitExceededError, ensure_document_slot

    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    await client.get(f"/organizations/{org}/billing/subscription", headers=_h(owner["token"]))
    await set_plan(org, plan_key)
    async with AsyncSessionLocal() as db:
        db.add_all([Document(organization_id=org, name=f"d{i}", file_key=f"k/{uuid.uuid4()}", file_size=1, file_type="text/plain", status="completed", created_by=owner["id"]) for i in range(limit - 1)])
        await db.commit()
    async with AsyncSessionLocal() as db:
        await ensure_document_slot(db, org)  # the limit-th document still fits
    async with AsyncSessionLocal() as db:
        db.add(Document(organization_id=org, name="last", file_key=f"k/{uuid.uuid4()}", file_size=1, file_type="text/plain", status="completed", created_by=owner["id"]))
        await db.commit()
    async with AsyncSessionLocal() as db:
        with pytest.raises(DocumentLimitExceededError):
            await ensure_document_slot(db, org)
    # the same state through HTTP: the upload route answers 402
    assert (await upload(client, owner, org, "over", expect=None)).status_code == 402
    await set_plan(org, "enterprise")  # no cap on Enterprise
    assert (await upload(client, owner, org, "enterprise-ok", expect=None)).status_code == 201


# ================================================================================================== 12.2.1 / 12.2.2 questions per day


async def test_free_plan_tenth_question_passes_eleventh_is_refused_with_402(client, _fake_llm_and_keys):
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    await client.get(f"/organizations/{org}/billing/credits", headers=_h(owner["token"]))
    await set_balance(org, 1000)
    _agent, key = await deployed_agent(client, owner, org)
    for i in range(1, 11):
        r = await ask(client, key, f"question {i}")
        assert r.status_code == 200 and r.json()["status"] == "completed", f"question {i}: {r.status_code} {r.text[:300]}"
    llm_calls_before = _fake_llm_and_keys.await_count
    r = await ask(client, key, "question 11")
    assert r.status_code == 402 and "Daily question limit reached" in r.json()["detail"] and "10 questions per day" in r.json()["detail"]
    assert _fake_llm_and_keys.await_count == llm_calls_before  # the refused question never reached the LLM...
    assert await credit_balance(org) == 1000 - 10 * CALL_COST  # ...and cost no credits
    assert await questions_today(org) == 10


async def test_a_question_refused_for_lack_of_credits_does_not_use_up_the_daily_quota(client, _fake_llm_and_keys):
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    await client.get(f"/organizations/{org}/billing/credits", headers=_h(owner["token"]))
    await set_balance(org, 0)
    _agent, key = await deployed_agent(client, owner, org)
    for _ in range(12):
        r = await ask(client, key)
        assert r.status_code == 402 and "Insufficient AI credits" in r.json()["detail"]
    assert _fake_llm_and_keys.await_count == 0
    assert await questions_today(org) == 0  # twelve refusals did not eat the 10 free questions


async def test_starter_allows_500_questions_a_day_pro_is_unlimited(client, _fake_llm_and_keys):
    from api.services.billing_usage import QuestionLimitExceededError, reserve_daily_question

    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    await client.get(f"/organizations/{org}/billing/subscription", headers=_h(owner["token"]))
    await set_plan(org, "starter")
    for _ in range(500):  # the 500 counted at the service level, in one transaction per question like the orchestrator does
        async with AsyncSessionLocal() as db:
            await reserve_daily_question(db, org, user_id=owner["id"])
            await db.commit()
    async with AsyncSessionLocal() as db:
        with pytest.raises(QuestionLimitExceededError):
            await reserve_daily_question(db, org)
    assert await questions_today(org) == 500
    await set_plan(org, "pro")  # upgrade: the same day's counter no longer limits anything
    async with AsyncSessionLocal() as db:
        await reserve_daily_question(db, org)
        await db.commit()
    assert await questions_today(org) == 501


async def test_concurrent_questions_cannot_exceed_the_daily_quota(client, _fake_llm_and_keys):
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    await client.get(f"/organizations/{org}/billing/credits", headers=_h(owner["token"]))
    await set_balance(org, 5000)
    _agent, key = await deployed_agent(client, owner, org)
    results = await asyncio.gather(*[ask(client, key, f"parallel {i}") for i in range(14)])
    codes = sorted(r.status_code for r in results)
    assert codes.count(200) == 10 and codes.count(402) == 4, codes
    assert await questions_today(org) == 10


async def test_the_daily_counter_is_per_day_and_per_organization(client, _fake_llm_and_keys):
    from api.services.billing_usage import reserve_daily_question

    await seed_catalogue(client)
    a, b = await new_user(client), await new_user(client)
    org_a, org_b = await new_org(client, a), await new_org(client, b)
    for org, owner in ((org_a, a), (org_b, b)):
        await client.get(f"/organizations/{org}/billing/subscription", headers=_h(owner["token"]))
    for _ in range(10):
        async with AsyncSessionLocal() as db:
            await reserve_daily_question(db, org_a)
            await db.commit()
    assert await questions_today(org_a) == 10 and await questions_today(org_b) == 0
    async with AsyncSessionLocal() as db:  # org B is unaffected by A's usage
        await reserve_daily_question(db, org_b)
        await db.commit()
    # yesterday's counter does not count today: move A's row to yesterday and the quota is open again
    async with AsyncSessionLocal() as db:
        await db.execute(update(OrganizationUsage).where(OrganizationUsage.organization_id == org_a, OrganizationUsage.metric == "questions").values(date=func.current_date() - 1))
        await db.commit()
    async with AsyncSessionLocal() as db:
        await reserve_daily_question(db, org_a)
        await db.commit()
    assert await questions_today(org_a) == 11  # 10 from yesterday + 1 today; the daily row of today is 1


# ================================================================================================== 12.1.6 / 12.1.7 upgrade and downgrade


async def test_self_service_upgrade_to_a_paid_plan_is_refused_without_payment_and_downgrade_works(client):
    plans = await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    base = f"/organizations/{org}/billing"
    # free -> pro through the self-service route: refused (402), the plan did not change
    r = await client.post(f"{base}/upgrade", headers=_h(owner["token"]), json={"plan_id": plans["pro"]["id"], "billing_period": "monthly"})
    assert r.status_code == 402
    assert (await client.get(f"{base}/subscription", headers=_h(owner["token"]))).json()["plan_id"] == plans["free"]["id"]
    # the provider confirms a payment (webhook, see below) -> pro; here the back-office/provider path
    await set_plan(org, "pro")
    assert (await client.get(f"{base}/subscription", headers=_h(owner["token"]))).json()["plan_id"] == plans["pro"]["id"]
    # pro -> starter is a downgrade: allowed without payment
    r = await client.post(f"{base}/downgrade", headers=_h(owner["token"]), json={"plan_id": plans["starter"]["id"], "billing_period": "monthly"})
    assert r.status_code == 200 and r.json()["plan_id"] == plans["starter"]["id"]
    # starter -> pro through "downgrade" would be a paid upgrade through the back door
    r = await client.post(f"{base}/downgrade", headers=_h(owner["token"]), json={"plan_id": plans["pro"]["id"], "billing_period": "monthly"})
    assert r.status_code in (400, 402)
    # an unknown plan is a 404, an inactive one too
    assert (await client.post(f"{base}/upgrade", headers=_h(owner["token"]), json={"plan_id": str(uuid.uuid4()), "billing_period": "monthly"})).status_code == 404


async def test_upgrade_endpoint_refuses_a_lower_plan_and_downgrade_a_higher_one(client):
    plans = await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    base = f"/organizations/{org}/billing"
    await client.get(f"{base}/subscription", headers=_h(owner["token"]))
    await set_plan(org, "pro")
    r = await client.post(f"{base}/upgrade", headers=_h(owner["token"]), json={"plan_id": plans["starter"]["id"], "billing_period": "monthly"})
    assert r.status_code == 400 and "downgrade" in r.json()["detail"].lower()
    r = await client.post(f"{base}/downgrade", headers=_h(owner["token"]), json={"plan_id": plans["business"]["id"], "billing_period": "monthly"})
    assert r.status_code in (400, 402)
    sub = (await client.get(f"{base}/subscription", headers=_h(owner["token"]))).json()
    assert sub["plan_id"] == plans["pro"]["id"]


async def test_downgrade_with_usage_above_the_new_limits_keeps_the_data_and_blocks_new_additions(client):
    plans = await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    base = f"/organizations/{org}/billing"
    await client.get(f"{base}/subscription", headers=_h(owner["token"]))
    await set_plan(org, "starter")
    async with AsyncSessionLocal() as db:  # 5 documents: fits Starter (100), exceeds Free (3)
        db.add_all([Document(organization_id=org, name=f"d{i}", file_key=f"k/{uuid.uuid4()}", file_size=1, file_type="text/plain", status="completed", created_by=owner["id"]) for i in range(5)])
        await db.commit()
    r = await client.post(f"{base}/downgrade", headers=_h(owner["token"]), json={"plan_id": plans["free"]["id"], "billing_period": "monthly"})
    assert r.status_code == 200 and r.json()["plan_id"] == plans["free"]["id"]  # the downgrade itself is not refused
    assert await doc_count(org) == 5  # no data is deleted by a downgrade
    over = await upload(client, owner, org, "one-more", expect=None)
    assert over.status_code == 402 and "3 documents" in over.json()["detail"] and "currently 5" in over.json()["detail"]
    listing = await client.get(f"/organizations/{org}/documents", headers=_h(owner["token"]))  # existing documents stay readable
    assert listing.status_code == 200
    # deleting down to the limit re-opens nothing until a slot is really free: 5 -> 3 documents still blocks, 2 re-opens
    async with AsyncSessionLocal() as db:
        rows = list((await db.scalars(select(Document).where(Document.organization_id == org))).all())
        for row in rows[:2]:
            row.deleted_at = func.now()
        await db.commit()
    assert (await upload(client, owner, org, "still-full", expect=None)).status_code == 402  # 3 live documents = at the limit
    async with AsyncSessionLocal() as db:
        row = (await db.scalars(select(Document).where(Document.organization_id == org, Document.deleted_at.is_(None)))).first()
        row.deleted_at = func.now()
        await db.commit()
    await upload(client, owner, org, "now-fits")


# ================================================================================================== 12.1.8 cancellation


async def test_local_cancel_then_reactivate_and_audit(client):
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    base = f"/organizations/{org}/billing"
    await client.get(f"{base}/subscription", headers=_h(owner["token"]))
    r = await client.post(f"{base}/cancel", headers=_h(owner["token"]), json={"reason": "too expensive"})
    assert r.status_code == 200 and r.json()["status"] == "canceled" and r.json()["canceled_at"]
    r = await client.post(f"{base}/reactivate", headers=_h(owner["token"]))
    assert r.status_code == 200 and r.json()["status"] == "active" and r.json()["canceled_at"] is None


async def test_cancel_of_a_paid_subscription_keeps_access_until_the_period_end_then_falls_back_to_free(client):
    from api.services.billing_usage import get_effective_plan
    import datetime as dt

    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    await client.get(f"/organizations/{org}/billing/subscription", headers=_h(owner["token"]))
    await set_plan(org, "pro")
    async with AsyncSessionLocal() as db:
        sub = await db.scalar(select(Subscription).where(Subscription.organization_id == org))
        sub.current_period_end = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=10)
        await db.commit()
    r = await client.post(f"/organizations/{org}/billing/cancel", headers=_h(owner["token"]), json={"reason": "leaving"})
    assert r.status_code == 200 and r.json()["status"] == "canceled"
    async with AsyncSessionLocal() as db:
        assert (await get_effective_plan(db, org)).key == "pro"  # paid period not over: pro limits still apply
    async with AsyncSessionLocal() as db:
        sub = await db.scalar(select(Subscription).where(Subscription.organization_id == org))
        sub.current_period_end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
        await db.commit()
    async with AsyncSessionLocal() as db:
        assert (await get_effective_plan(db, org)).key == "free"  # period over: Free limits apply (3 documents, 10 questions)


async def test_cancel_and_reactivate_are_forbidden_to_a_member_and_a_viewer_and_to_outsiders(client):
    plans = await seed_catalogue(client)
    owner, member, viewer, outsider = [await new_user(client) for _ in range(4)]
    org = await new_org(client, owner)
    await add_member(org, member, OrganizationRole.member)
    await add_member(org, viewer, OrganizationRole.viewer)
    base = f"/organizations/{org}/billing"
    for who in (member, viewer):
        assert (await client.post(f"{base}/cancel", headers=_h(who["token"]), json={})).status_code == 403
        assert (await client.post(f"{base}/reactivate", headers=_h(who["token"]))).status_code == 403
        assert (await client.post(f"{base}/upgrade", headers=_h(who["token"]), json={"plan_id": plans["starter"]["id"], "billing_period": "monthly"})).status_code == 403
        assert (await client.post(f"{base}/credits/purchase", headers=_h(who["token"]), json={"pack_id": "starter"})).status_code == 403
    assert (await client.post(f"{base}/cancel", headers=_h(outsider["token"]), json={})).status_code in (403, 404)
    assert (await client.get(f"{base}/subscription", headers=_h(outsider["token"]))).status_code in (403, 404)
    assert (await client.get(f"{base}/credits", headers=_h(outsider["token"]))).status_code in (403, 404)
    assert (await client.get(f"{base}/subscription", headers=_h(viewer["token"]))).status_code == 403  # billing:read is not granted to a viewer
    sub = (await client.get(f"{base}/subscription", headers=_h(owner["token"]))).json()
    assert sub["status"] == "active"  # nothing above changed it


# ================================================================================================== 12.1.2 recurring subscription, idempotent provider events


@pytest.fixture
def stripe_cfg(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_local_fake_never_used_for_network")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_local_fake_secret")
    return "whsec_local_fake_secret"


async def test_stripe_style_subscription_lifecycle_through_signed_events_is_idempotent(client, stripe_cfg):
    """checkout -> active paid plan -> renewal extends the period -> payment failure -> past_due -> recovery -> cancellation at period end -> deletion.
    The events are produced locally and signed with Stripe's documented scheme; the route verifies them with the real stripe SDK."""
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    await client.get(f"/organizations/{org}/billing/subscription", headers=_h(owner["token"]))
    async with AsyncSessionLocal() as db:
        pro = await db.scalar(select(Plan).where(Plan.key == "pro"))
        pro.stripe_price_id_monthly = f"price_local_{uuid.uuid4().hex[:8]}"
        price = pro.stripe_price_id_monthly
        await db.commit()
    sub_id = f"sub_local_{uuid.uuid4().hex[:8]}"
    now = int(time.time())
    period1, period2 = now + 30 * 86400, now + 60 * 86400

    def sub_obj(status, end, **extra):
        return {"id": sub_id, "object": "subscription", "status": status, "current_period_end": end, "metadata": {"organization_id": str(org)},
                "items": {"data": [{"price": {"id": price}}]}, **extra}

    async def post(event_type, obj, event_id=None):
        event = {"id": event_id or f"evt_{uuid.uuid4().hex}", "type": event_type, "data": {"object": obj}}
        payload, headers = stripe_signed(event, stripe_cfg)
        return event, await client.post("/billing/stripe/webhook", content=payload, headers=headers)

    async def state():
        return (await client.get(f"/organizations/{org}/billing/subscription", headers=_h(owner["token"]))).json()

    # signature checks first: forged / missing signatures are refused and change nothing
    payload, headers = stripe_signed({"id": "evt_x", "type": "customer.subscription.created", "data": {"object": sub_obj("active", period1)}}, "whsec_wrong")
    assert (await client.post("/billing/stripe/webhook", content=payload, headers=headers)).status_code == 400
    assert (await client.post("/billing/stripe/webhook", content=payload)).status_code == 400
    assert (await state())["plan_id"] != (await seed_catalogue(client))["pro"]["id"]

    event, r = await post("customer.subscription.created", sub_obj("active", period1))
    assert r.status_code == 200 and r.json() == {"received": True, "applied": True}
    s = await state()
    assert s["status"] == "active" and s["plan_id"] == (await seed_catalogue(client))["pro"]["id"] and await stripe_sub_id(org) == sub_id
    # the same event delivered again (Stripe retries): acknowledged, not re-applied
    payload, headers = stripe_signed(event, stripe_cfg)
    r = await client.post("/billing/stripe/webhook", content=payload, headers=headers)
    assert r.status_code == 200 and r.json()["applied"] is False
    # five concurrent deliveries of one NEW event: applied exactly once
    renewal = {"id": f"evt_{uuid.uuid4().hex}", "type": "invoice.paid", "data": {"object": {"id": f"in_{uuid.uuid4().hex[:8]}", "subscription": sub_id, "metadata": {"organization_id": str(org)}, "lines": {"data": [{"period": {"end": period2}}]}}}}
    payload, headers = stripe_signed(renewal, stripe_cfg)
    results = await asyncio.gather(*[client.post("/billing/stripe/webhook", content=payload, headers=headers) for _ in range(5)])
    assert sorted(r.json()["applied"] for r in results if r.status_code == 200).count(True) == 1
    assert [r.status_code for r in results].count(200) >= 1
    async with AsyncSessionLocal() as db:
        n = await db.scalar(select(func.count()).select_from(PaymentEvent).where(PaymentEvent.id == renewal["id"]))
        assert n == 1
    assert int(__import__("datetime").datetime.fromisoformat((await state())["current_period_end"].replace("Z", "+00:00")).timestamp()) == period2  # renewal extended the period

    await post("invoice.payment_failed", {"id": "in_fail", "subscription": sub_id, "metadata": {"organization_id": str(org)}})
    assert (await state())["status"] == "past_due"
    await post("invoice.paid", {"id": "in_ok", "subscription": sub_id, "metadata": {"organization_id": str(org)}, "lines": {"data": [{"period": {"end": period2 + 86400}}]}})
    assert (await state())["status"] == "active"
    # cancel at period end (the customer used the portal): access stays, canceled_at is recorded
    await post("customer.subscription.updated", sub_obj("active", period2, cancel_at_period_end=True))
    s = await state()
    assert s["status"] == "active" and s["canceled_at"] is not None
    # a stale event for ANOTHER subscription does not touch the current one
    await post("customer.subscription.deleted", {"id": "sub_some_old_one", "object": "subscription", "status": "canceled", "metadata": {"organization_id": str(org)}})
    assert (await state())["status"] == "active"
    await post("customer.subscription.deleted", sub_obj("canceled", period2))
    assert (await state())["status"] == "canceled"
    # a late "active" event for the ended subscription never reopens it
    await post("customer.subscription.updated", sub_obj("active", period2))
    assert (await state())["status"] == "canceled"


async def test_stripe_event_about_another_organization_is_not_applied_to_this_one(client, stripe_cfg):
    await seed_catalogue(client)
    a, b = await new_user(client), await new_user(client)
    org_a, org_b = await new_org(client, a), await new_org(client, b)
    for org, u in ((org_a, a), (org_b, b)):
        await client.get(f"/organizations/{org}/billing/subscription", headers=_h(u["token"]))
    event = {"id": f"evt_{uuid.uuid4().hex}", "type": "invoice.payment_failed", "data": {"object": {"id": "in_1", "subscription": "sub_a", "metadata": {"organization_id": str(org_a)}}}}
    payload, headers = stripe_signed(event, stripe_cfg)
    assert (await client.post("/billing/stripe/webhook", content=payload, headers=headers)).status_code == 200
    sa = (await client.get(f"/organizations/{org_a}/billing/subscription", headers=_h(a["token"]))).json()
    sb = (await client.get(f"/organizations/{org_b}/billing/subscription", headers=_h(b["token"]))).json()
    assert sa["status"] == "past_due"  # the event named organization A...
    assert sb["status"] == "active"  # ...and B, which the event did not name, is untouched


async def stripe_sub_id(org_id) -> str | None:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(Subscription.stripe_subscription_id).where(Subscription.organization_id == org_id))


async def paystack_code(org_id) -> str | None:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(Subscription.paystack_subscription_code).where(Subscription.organization_id == org_id))


@pytest.fixture
def paystack_cfg(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_local_paystack_fake")
    return "sk_test_local_paystack_fake"


async def test_paystack_style_events_are_signed_idempotent_and_ordered(client, paystack_cfg):
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    code = f"PLN_local_{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        starter = await db.scalar(select(Plan).where(Plan.key == "starter"))
        starter.paystack_plan_code_monthly = code
        await db.commit()
    sub_code = f"SUB_{uuid.uuid4().hex[:8]}"
    base_id = uuid.uuid4().int % 10**12  # Paystack object ids are unique per event; fresh ones per run

    async def state():
        return (await client.get(f"/organizations/{org}/billing/subscription", headers=_h(owner["token"]))).json()

    await state()
    created = {"event": "subscription.create", "data": {"id": base_id, "subscription_code": sub_code, "plan": {"plan_code": code}, "metadata": {"organization_id": str(org)}}}
    bad_payload, bad_headers = paystack_signed(created, "sk_wrong")
    assert (await client.post("/billing/paystack/webhook", content=bad_payload, headers=bad_headers)).status_code == 400
    payload, headers = paystack_signed(created, paystack_cfg)
    r = await client.post("/billing/paystack/webhook", content=payload, headers=headers)
    assert r.status_code == 200 and r.json()["applied"] is True
    assert (await state())["plan_id"] == (await seed_catalogue(client))["starter"]["id"] and await paystack_code(org) == sub_code
    r = await client.post("/billing/paystack/webhook", content=payload, headers=headers)  # redelivery
    assert r.json()["applied"] is False
    failed = {"event": "invoice.payment_failed", "data": {"id": base_id + 1, "subscription_code": sub_code, "metadata": {"organization_id": str(org)}}}
    payload, headers = paystack_signed(failed, paystack_cfg)
    with patch("api.services.notifications.notify_billing_payment_failed", new=AsyncMock()):
        r = await client.post("/billing/paystack/webhook", content=payload, headers=headers)
    assert r.status_code == 200 and r.json()["applied"] is True, r.text
    assert (await state())["status"] == "past_due"
    ok = {"event": "charge.success", "data": {"id": base_id + 2, "subscription_code": sub_code, "metadata": {"organization_id": str(org)}}}
    payload, headers = paystack_signed(ok, paystack_cfg)
    await client.post("/billing/paystack/webhook", content=payload, headers=headers)
    assert (await state())["status"] == "active"
    disabled = {"event": "subscription.disable", "data": {"id": base_id + 3, "subscription_code": sub_code, "metadata": {"organization_id": str(org)}}}
    payload, headers = paystack_signed(disabled, paystack_cfg)
    await client.post("/billing/paystack/webhook", content=payload, headers=headers)
    assert (await state())["status"] == "canceled"
    late_create_payload, late_create_headers = paystack_signed({**created, "data": {**created["data"], "id": base_id + 4}}, paystack_cfg)
    await client.post("/billing/paystack/webhook", content=late_create_payload, headers=late_create_headers)
    assert (await state())["status"] == "canceled"  # a disabled subscription is never revived by a late create


# ================================================================================================== 12.1.10 / 12.3.1 credits


async def test_credits_are_consumed_per_answer_and_the_ledger_matches_the_balance(client, _fake_llm_and_keys):
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    base = f"/organizations/{org}/billing"
    assert (await client.get(f"{base}/credits", headers=_h(owner["token"]))).json()["balance"] == settings.CREDITS_DEFAULT_AMOUNT  # the signup allotment
    _agent, key = await deployed_agent(client, owner, org)
    for _ in range(3):
        assert (await ask(client, key)).status_code == 200
    expected = settings.CREDITS_DEFAULT_AMOUNT - 3 * CALL_COST
    assert (await client.get(f"{base}/credits", headers=_h(owner["token"]))).json()["balance"] == expected
    tx = (await client.get(f"{base}/credits/transactions", headers=_h(owner["token"]))).json()
    consumed = [t for t in tx if t["type"] == "consume"]
    assert len(consumed) == 3 and all(t["amount"] == -CALL_COST for t in consumed)
    assert consumed[0]["balance_after"] == expected  # newest first
    async with AsyncSessionLocal() as db:  # ledger invariant: the sum of all transactions is the balance
        total = await db.scalar(select(func.coalesce(func.sum(CreditTransaction.amount), 0)).where(CreditTransaction.organization_id == org))
        assert int(total) == expected


async def test_an_empty_balance_refuses_every_question_before_any_llm_call_and_recovers_after_a_top_up(client, _fake_llm_and_keys, monkeypatch):
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    base = f"/organizations/{org}/billing"
    await client.get(f"{base}/credits", headers=_h(owner["token"]))
    await set_balance(org, CALL_COST)  # exactly one answer left
    _agent, key = await deployed_agent(client, owner, org)
    assert (await ask(client, key)).status_code == 200
    assert await credit_balance(org) == 0
    calls = _fake_llm_and_keys.await_count
    r = await ask(client, key)
    assert r.status_code == 402 and "Insufficient AI credits" in r.json()["detail"]
    assert _fake_llm_and_keys.await_count == calls and await credit_balance(org) == 0  # never negative, nothing served for free
    # the top-up route (self-hosted opt-in only) restores service
    monkeypatch.setattr(settings, "CREDITS_ALLOW_UNPAID_TOPUP", True)
    packs = (await client.get(f"{base}/credits/packs", headers=_h(owner["token"]))).json()
    pack = packs[0]
    r = await client.post(f"{base}/credits/purchase", headers=_h(owner["token"]), json={"pack_id": pack["id"]})
    assert r.status_code == 200 and r.json()["balance"] == pack["credits"]
    assert (await ask(client, key)).status_code == 200
    # and with the opt-in off (production default) the free top-up is refused
    monkeypatch.setattr(settings, "CREDITS_ALLOW_UNPAID_TOPUP", False)
    assert (await client.post(f"{base}/credits/purchase", headers=_h(owner["token"]), json={"pack_id": pack["id"]})).status_code == 403
    assert (await client.post(f"{base}/credits/purchase", headers=_h(owner["token"]), json={"pack_id": "no-such-pack"})).status_code in (403, 404)


async def test_byok_organizations_do_not_spend_platform_credits(client, _fake_llm_and_keys):
    from api.services import llm_byok

    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    await client.get(f"/organizations/{org}/billing/credits", headers=_h(owner["token"]))
    await set_balance(org, 0)
    _agent, key = await deployed_agent(client, owner, org)
    with patch.object(llm_byok, "resolve_org_api_key", new=AsyncMock(return_value="sk-ant-customer-own-key")), \
         patch("api.services.agent_orchestrator.resolve_org_api_key", new=AsyncMock(return_value="sk-ant-customer-own-key")):
        r = await ask(client, key)
    assert r.status_code == 200 and await credit_balance(org) == 0  # answered, billed to the customer's own provider account


async def test_credit_pack_purchase_through_a_signed_stripe_event_is_granted_exactly_once(client, stripe_cfg):
    from api.security.credit_packs import CREDIT_PACKS

    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    await client.get(f"/organizations/{org}/billing/credits", headers=_h(owner["token"]))
    before = await credit_balance(org)
    pack = CREDIT_PACKS[0]
    session = {"id": f"cs_local_{uuid.uuid4().hex[:8]}", "object": "checkout.session", "mode": "payment", "payment_status": "paid", "amount_total": pack["price_cents"],
               "currency": settings.CREDIT_PACK_CURRENCY, "metadata": {"kind": "credit_pack", "pack_id": pack["id"], "organization_id": str(org)}}
    first = {"id": f"evt_{uuid.uuid4().hex}", "type": "checkout.session.completed", "data": {"object": session}}
    replay_other_id = {"id": f"evt_{uuid.uuid4().hex}", "type": "checkout.session.async_payment_succeeded", "data": {"object": session}}  # same checkout session, new event id
    for event in (first, first, replay_other_id):
        payload, headers = stripe_signed(event, stripe_cfg)
        assert (await client.post("/billing/stripe/webhook", content=payload, headers=headers)).status_code == 200
    assert await credit_balance(org) == before + pack["credits"]  # once, not three times
    # a tampered amount or an unpaid session grants nothing
    for patch_session in ({"amount_total": 1}, {"payment_status": "unpaid"}):
        event = {"id": f"evt_{uuid.uuid4().hex}", "type": "checkout.session.completed", "data": {"object": {**session, "id": f"cs_local_{uuid.uuid4().hex[:8]}", **patch_session}}}
        payload, headers = stripe_signed(event, stripe_cfg)
        assert (await client.post("/billing/stripe/webhook", content=payload, headers=headers)).status_code == 200
    assert await credit_balance(org) == before + pack["credits"]


async def test_credit_endpoints_are_tenant_isolated(client):
    await seed_catalogue(client)
    a, b = await new_user(client), await new_user(client)
    org_a, org_b = await new_org(client, a), await new_org(client, b)
    await set_balance(org_a, 12345)
    mine = (await client.get(f"/organizations/{org_a}/billing/credits", headers=_h(a["token"]))).json()
    assert mine["balance"] == 12345
    assert (await client.get(f"/organizations/{org_a}/billing/credits", headers=_h(b["token"]))).status_code in (403, 404)
    assert (await client.get(f"/organizations/{org_a}/billing/credits/transactions", headers=_h(b["token"]))).status_code in (403, 404)
    theirs = (await client.get(f"/organizations/{org_b}/billing/credits", headers=_h(b["token"]))).json()
    assert theirs["balance"] == settings.CREDITS_DEFAULT_AMOUNT


async def test_concurrent_answers_never_drive_the_balance_negative(client, _fake_llm_and_keys):
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    await client.get(f"/organizations/{org}/billing/credits", headers=_h(owner["token"]))
    await set_balance(org, 3 * CALL_COST)
    await set_plan(org, "pro")  # unlimited questions: only credits are in play
    _agent, key = await deployed_agent(client, owner, org)
    await asyncio.gather(*[ask(client, key, f"parallel {i}") for i in range(8)])
    assert await credit_balance(org) >= 0
    # every served answer was paid for: balance + 5 per served answer = the starting balance (a partial last debit is recorded as such)
    async with AsyncSessionLocal() as db:
        spent = -int(await db.scalar(select(func.coalesce(func.sum(CreditTransaction.amount), 0)).where(CreditTransaction.organization_id == org, CreditTransaction.type == CreditTransactionType.consume)))
    assert spent == 3 * CALL_COST - await credit_balance(org)


# ================================================================================================== 5.3.10 deploy an agent to production


async def test_only_an_active_agent_answers_through_its_api_key(client, _fake_llm_and_keys):
    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    await client.get(f"/organizations/{org}/billing/credits", headers=_h(owner["token"]))
    agent_id, key = await deployed_agent(client, owner, org)
    assert (await ask(client, key)).status_code == 200  # deployed (active)
    assert (await client.post(f"/agents/{agent_id}/pause", headers=_h(owner["token"]))).status_code == 200
    calls = _fake_llm_and_keys.await_count
    r = await ask(client, key)
    assert r.status_code == 409 and "not deployed" in r.json()["detail"]  # paused: the key opens nothing
    assert _fake_llm_and_keys.await_count == calls
    assert (await client.post(f"/agents/{agent_id}/activate", headers=_h(owner["token"]))).status_code == 200
    assert (await ask(client, key)).status_code == 200  # redeployed
    assert (await client.post(f"/agents/{agent_id}/archive", headers=_h(owner["token"]))).status_code == 200
    assert (await ask(client, key)).status_code == 409


async def test_a_paused_agent_does_not_answer_through_the_orchestrator_whatever_the_door(client, _fake_llm_and_keys):
    from api.services.agent_orchestrator import AgentOrchestrator

    await seed_catalogue(client)
    owner = await new_user(client)
    org = await new_org(client, owner)
    agent_id, _key = await deployed_agent(client, owner, org)
    assert (await client.post(f"/agents/{agent_id}/pause", headers=_h(owner["token"]))).status_code == 200
    async with AsyncSessionLocal() as db:
        run = await AgentOrchestrator().run_agent(agent_id, "hello", db=db, organization_id=org, created_by=owner["id"])
    assert run.status == "failed" and "Agent not deployed" in run.error
    async with AsyncSessionLocal() as db:
        events = [e async for e in AgentOrchestrator().stream_response(agent_id, "hello", db=db, organization_id=org, created_by=owner["id"])]
    assert any(e.get("type") == "error" and "Agent not deployed" in e.get("error", "") for e in events)
    assert _fake_llm_and_keys.await_count == 0


async def test_agent_keys_are_scoped_to_their_agent_and_organization_and_revocable(client, _fake_llm_and_keys):
    await seed_catalogue(client)
    a, b = await new_user(client), await new_user(client)
    org_a, org_b = await new_org(client, a), await new_org(client, b)
    agent_a, key_a = await deployed_agent(client, a, org_a)
    agent_b, key_b = await deployed_agent(client, b, org_b)
    # B cannot mint or list keys for A's agent, nor revoke them
    assert (await client.post(f"/agents/{agent_a}/api-keys", headers=_h(b["token"]), json={"name": "x", "scopes": ["execute"]})).status_code in (403, 404)
    assert (await client.get(f"/agents/{agent_a}/api-keys", headers=_h(b["token"]))).status_code in (403, 404)
    # a read-only key cannot run the agent
    ro = await client.post(f"/agents/{agent_a}/api-keys", headers=_h(a["token"]), json={"name": "ro", "scopes": ["read"]})
    assert (await ask(client, ro.json()["key"])).status_code == 403
    # runs are billed to the key's own organization
    before_a, before_b = await credit_balance(org_a), await credit_balance(org_b)
    assert (await ask(client, key_a)).status_code == 200
    assert await credit_balance(org_b) == before_b and await credit_balance(org_a) == (before_a if before_a is not None else settings.CREDITS_DEFAULT_AMOUNT) - CALL_COST
    # revocation takes effect at once
    listing = (await client.get(f"/agents/{agent_a}/api-keys", headers=_h(a["token"]))).json()
    prod = next(k for k in listing if k["name"] == "prod")
    assert (await client.delete(f"/agents/{agent_a}/api-keys/{prod['id']}", headers=_h(a["token"]))).status_code == 204
    assert (await ask(client, key_a)).status_code == 401
    assert (await ask(client, "ak_not_a_real_key")).status_code == 401
