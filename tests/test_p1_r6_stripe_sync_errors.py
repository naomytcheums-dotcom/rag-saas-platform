"""R6: a Stripe catalogue sync that fails midway answers a clean 502, is audited, and keeps the ids already obtained so a retry does not
create duplicate products at Stripe. (Mocked Stripe: nothing leaves the process.)"""

from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from api.models.admin import Plan
from api.models.audit_log import AuditLog
from api.models.user import UserRole
from api.services import admin_subscriptions, billing_stripe_sync
from test_p1_backoffice_and_suspension import _bearer, _platform_user


async def _two_paid_plans(db_session):
    await admin_subscriptions.ensure_default_plans_seeded(db_session)
    plans = (await db_session.scalars(select(Plan).where(Plan.monthly_price_cents > 0, Plan.is_active.is_(True)).order_by(Plan.monthly_price_cents))).all()
    assert len(plans) >= 2, "the default catalogue has at least two paid plans"
    for plan in plans:
        plan.stripe_product_id = None
    ids = [plan.id for plan in plans]
    await db_session.commit()
    return ids


async def _product_ids(db_session, ids):
    db_session.expire_all()
    return {plan.id: plan.stripe_product_id for plan in (await db_session.scalars(select(Plan).where(Plan.id.in_(ids)))).all()}


async def test_a_midway_failure_is_a_clean_502_keeps_the_ids_obtained_and_is_audited(client, db_session):
    ids = await _two_paid_plans(db_session)
    superadmin = await _platform_user(db_session, "super-r6@example.com", UserRole.superadmin)
    headers = _bearer(superadmin.id)
    created = AsyncMock(side_effect=[{"id": "prod_1"}, RuntimeError("stripe exploded: sk_test_SECRET_DETAIL")])
    with patch.object(billing_stripe_sync, "_client", lambda: object()), patch.object(billing_stripe_sync, "create_stripe_product", created):
        response = await client.post("/admin/plans/sync/stripe-products", headers=headers)
    assert response.status_code == 502, response.text
    assert "SECRET_DETAIL" not in response.text and "exploded" not in response.text

    kept = await _product_ids(db_session, ids)
    assert sorted(v for v in kept.values() if v) == ["prod_1"], "the product created before the failure must stay recorded"

    db_session.expire_all()
    rows = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "admin_provider_sync"))).all()
    assert len(rows) == 1 and rows[0].success is False and rows[0].failure_reason == "provider error"
    assert "RuntimeError" in rows[0].metadata_json and "SECRET_DETAIL" not in rows[0].metadata_json


async def test_a_retry_creates_only_what_is_missing(client, db_session):
    ids = await _two_paid_plans(db_session)
    superadmin = await _platform_user(db_session, "super-r6retry@example.com", UserRole.superadmin)
    headers = _bearer(superadmin.id)
    with patch.object(billing_stripe_sync, "_client", lambda: object()), \
            patch.object(billing_stripe_sync, "create_stripe_product", AsyncMock(side_effect=[{"id": "prod_1"}, RuntimeError("boom")])):
        assert (await client.post("/admin/plans/sync/stripe-products", headers=headers)).status_code == 502
    retry = AsyncMock(side_effect=[{"id": f"prod_{n}"} for n in range(2, 9)])
    with patch.object(billing_stripe_sync, "_client", lambda: object()), patch.object(billing_stripe_sync, "create_stripe_product", retry):
        assert (await client.post("/admin/plans/sync/stripe-products", headers=headers)).status_code == 200
    assert retry.await_count == len(ids) - 1, "only the plans without a product are created again"
    assert all((await _product_ids(db_session, ids)).values())


async def test_the_not_configured_case_is_still_a_501(client, db_session):
    superadmin = await _platform_user(db_session, "super-r6conf@example.com", UserRole.superadmin)
    assert (await client.post("/admin/plans/sync/stripe-prices", headers=_bearer(superadmin.id))).status_code == 501
