"""Spec 12.1.4 -- promo codes. Fast SQLite suite."""

import datetime as dt
import uuid

from sqlalchemy import select

from api.models.billing import Credit, CreditTransaction, CreditTransactionType
from api.models.coupon import Coupon
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User, UserRole


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, db_session, email: str):
    token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    return token, await db_session.scalar(select(User).where(User.email == email))


async def _superadmin(client, db_session, email="coupon-admin@example.com"):
    token, user = await _register(client, db_session, email)
    user.role = UserRole.superadmin
    await db_session.commit()
    return token


async def _org(client, db_session, email):
    token, _user = await _register(client, db_session, email)
    org = (await client.post("/organizations", json={"name": f"Org {email}"}, headers=_h(token))).json()
    return token, org["id"]


async def _create(client, admin, **kw):
    body = {"code": "WELCOME50", "kind": "bonus_credits", "bonus_credits": 50, **kw}
    return await client.post("/admin/coupons", json=body, headers=_h(admin))


async def test_only_a_superadmin_can_create_or_list_coupons(client, db_session):
    token, _org_id = await _org(client, db_session, "coupon-plain@example.com")
    assert (await _create(client, token)).status_code in (403, 404)
    assert (await client.get("/admin/coupons", headers=_h(token))).status_code in (403, 404)


async def test_create_validates_the_kind_and_rejects_duplicates(client, db_session):
    admin = await _superadmin(client, db_session)
    ok = await _create(client, admin)
    assert ok.status_code == 201 and ok.json()["code"] == "WELCOME50" and ok.json()["redeemed_count"] == 0
    assert (await _create(client, admin, code="welcome50")).status_code == 409
    assert (await _create(client, admin, code="NOCREDITS", bonus_credits=None)).status_code == 422
    assert (await _create(client, admin, code="BOTH", kind="percent_off", percent_off=10)).status_code == 422
    assert (await _create(client, admin, code="OVER", kind="percent_off", bonus_credits=None, percent_off=101)).status_code == 422


async def test_redeeming_adds_credits_once_as_a_grant(client, db_session):
    admin = await _superadmin(client, db_session)
    await _create(client, admin)
    token, org_id = await _org(client, db_session, "coupon-org@example.com")
    url = f"/organizations/{org_id}/billing/coupons/redeem"
    first = await client.post(url, json={"code": "welcome50"}, headers=_h(token))
    assert first.status_code == 200 and first.json()["bonus_credits"] == 50
    credit = await db_session.scalar(select(Credit).where(Credit.organization_id == uuid.UUID(org_id)))
    await db_session.refresh(credit)
    signup_grant = next(t for t in (await db_session.scalars(select(CreditTransaction).where(CreditTransaction.organization_id == uuid.UUID(org_id)))).all() if not (t.reason or "").startswith("coupon:"))
    assert credit.balance == signup_grant.amount + 50  # the free signup credits plus the coupon
    tx = (await db_session.scalars(select(CreditTransaction).where(CreditTransaction.organization_id == uuid.UUID(org_id)))).all()
    coupon_tx = [t for t in tx if (t.reason or "").startswith("coupon:")]
    assert [(t.type, t.reason, t.amount) for t in coupon_tx] == [(CreditTransactionType.grant, "coupon:WELCOME50", 50)]
    assert (await client.post(url, json={"code": "WELCOME50"}, headers=_h(token))).status_code == 400  # once per organization


async def test_the_global_redemption_limit_is_enforced(client, db_session):
    admin = await _superadmin(client, db_session)
    await _create(client, admin, code="ONLYONE", max_redemptions=1)
    t1, o1 = await _org(client, db_session, "coupon-first@example.com")
    t2, o2 = await _org(client, db_session, "coupon-second@example.com")
    assert (await client.post(f"/organizations/{o1}/billing/coupons/redeem", json={"code": "ONLYONE"}, headers=_h(t1))).status_code == 200
    assert (await client.post(f"/organizations/{o2}/billing/coupons/redeem", json={"code": "ONLYONE"}, headers=_h(t2))).status_code == 400
    coupon = await db_session.scalar(select(Coupon).where(Coupon.code == "ONLYONE"))
    await db_session.refresh(coupon)
    assert coupon.redeemed_count == 1


async def test_expired_inactive_and_unknown_codes_are_all_rejected_the_same_way(client, db_session):
    admin = await _superadmin(client, db_session)
    await _create(client, admin, code="EXPIRED", expires_at=(dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).isoformat())
    made = await _create(client, admin, code="OFFCODE")
    await client.patch(f"/admin/coupons/{made.json()['id']}", json={"active": False}, headers=_h(admin))
    token, org_id = await _org(client, db_session, "coupon-bad@example.com")
    url = f"/organizations/{org_id}/billing/coupons/redeem"
    responses = [await client.post(url, json={"code": c}, headers=_h(token)) for c in ("EXPIRED", "OFFCODE", "NOPE")]
    assert {r.status_code for r in responses} == {400}
    assert len({r.json()["detail"] for r in responses}) == 1  # no hint about which case it was


async def test_percent_off_is_recorded_without_touching_credits(client, db_session):
    admin = await _superadmin(client, db_session)
    await _create(client, admin, code="TEN10", kind="percent_off", bonus_credits=None, percent_off=10)
    token, org_id = await _org(client, db_session, "coupon-percent@example.com")
    r = await client.post(f"/organizations/{org_id}/billing/coupons/redeem", json={"code": "TEN10"}, headers=_h(token))
    assert r.status_code == 200 and r.json()["percent_off"] == 10 and "not applied automatically" in r.json()["message"]
    assert await db_session.scalar(select(Credit).where(Credit.organization_id == uuid.UUID(org_id))) is None


async def test_only_an_organization_admin_can_redeem(client, db_session):
    admin = await _superadmin(client, db_session)
    await _create(client, admin)
    owner_token, org_id = await _org(client, db_session, "coupon-owner2@example.com")
    member_token, member = await _register(client, db_session, "coupon-member@example.com")
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org_id), user_id=member.id, role=OrganizationRole.member))
    await db_session.commit()
    assert (await client.post(f"/organizations/{org_id}/billing/coupons/redeem", json={"code": "WELCOME50"}, headers=_h(member_token))).status_code == 403
    assert owner_token
