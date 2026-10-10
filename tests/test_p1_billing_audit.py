"""V9: every state-changing billing action of an organization leaves an audit row scoped to that organization, written with the change.

Before: subscribe/upgrade/downgrade, cancel, reactivate, direct credit top-up, billing country and payment-method removal wrote no audit
row at all, so a plan change, a cancellation or a credit grant could not be attributed to anyone. Refused or failed actions must not
leave a row (nothing happened), and an organization only ever sees its own rows.
"""

from unittest.mock import MagicMock, patch

from sqlalchemy import select

from api.config import settings
from api.models.admin import Plan
from api.models.audit_log import AuditLog
from api.services import admin_subscriptions, billing_stripe
from test_document_idor import make_tenants
from test_p1_bill003_005_006_stripe_chain import _provider_managed

BILLING_ACTIONS = (
    "billing_plan_changed", "billing_subscription_canceled", "billing_subscription_reactivated",
    "billing_credits_added", "billing_country_changed", "billing_payment_method_removed",
)


async def _rows(db_session, org_id=None):
    db_session.expire_all()
    query = select(AuditLog).where(AuditLog.action.in_(BILLING_ACTIONS)).order_by(AuditLog.timestamp, AuditLog.id)
    if org_id is not None:
        query = query.where(AuditLog.organization_id == org_id)
    return list((await db_session.scalars(query)).all())


async def _tenant(client, db_session, monkeypatch, label):
    (headers, org_id, user_id), (headers_b, org_b, _user_b) = await make_tenants(client, db_session, monkeypatch, label)
    await admin_subscriptions.ensure_default_plans_seeded(db_session)
    plans = {plan.key: plan.id for plan in (await db_session.scalars(select(Plan))).all()}
    await db_session.commit()
    return headers, org_id, user_id, headers_b, org_b, plans


async def test_a_plan_change_is_audited_with_before_and_after(client, db_session, monkeypatch):
    headers, org_id, user_id, _hb, _ob, plans = await _tenant(client, db_session, monkeypatch, "auditplan")
    response = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": str(plans["free"])}, headers=headers)
    assert response.status_code == 200, response.text
    rows = await _rows(db_session, org_id)
    assert len(rows) == 1 and rows[0].action == "billing_plan_changed" and rows[0].user_id == user_id
    assert str(plans["free"]) in rows[0].metadata_json and '"before"' in rows[0].metadata_json and '"after"' in rows[0].metadata_json


async def test_a_refused_plan_change_leaves_no_row(client, db_session, monkeypatch):
    headers, org_id, _u, _hb, _ob, plans = await _tenant(client, db_session, monkeypatch, "auditrefused")
    response = await client.post(f"/organizations/{org_id}/billing/upgrade", json={"plan_id": str(plans["pro"])}, headers=headers)
    assert response.status_code == 402
    assert await _rows(db_session, org_id) == []


async def test_cancel_and_reactivate_are_audited(client, db_session, monkeypatch):
    headers, org_id, _u, _hb, _ob, _plans = await _tenant(client, db_session, monkeypatch, "auditcancel")
    assert (await client.post(f"/organizations/{org_id}/billing/cancel", json={"reason": "x"}, headers=headers)).status_code == 200
    assert (await client.post(f"/organizations/{org_id}/billing/reactivate", headers=headers)).status_code == 200
    assert [row.action for row in await _rows(db_session, org_id)] == ["billing_subscription_canceled", "billing_subscription_reactivated"]


async def test_cancelling_at_the_provider_is_audited_and_a_provider_failure_is_not(client, db_session, monkeypatch):
    headers, org_id, _plans = await _provider_managed(client, db_session, monkeypatch, "auditprov")
    failing = MagicMock()
    failing.Subscription.modify.side_effect = RuntimeError("down")
    with patch.object(billing_stripe, "_client", return_value=failing):
        assert (await client.post(f"/organizations/{org_id}/billing/cancel", json={"reason": None}, headers=headers)).status_code == 502
    assert await _rows(db_session, org_id) == [], "nothing happened, nothing to audit"
    with patch.object(billing_stripe, "_client", return_value=MagicMock()):
        assert (await client.post(f"/organizations/{org_id}/billing/cancel", json={"reason": None}, headers=headers)).status_code == 200
        assert (await client.post(f"/organizations/{org_id}/billing/stripe/cancel", headers=headers)).status_code == 204
    rows = await _rows(db_session, org_id)
    assert [row.action for row in rows] == ["billing_subscription_canceled"] * 2
    assert '"via": "provider"' in rows[0].metadata_json and '"via": "stripe"' in rows[1].metadata_json


async def test_a_direct_credit_top_up_is_audited_as_unpaid(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "CREDITS_ALLOW_UNPAID_TOPUP", True)
    headers, org_id, _u, _hb, _ob, _plans = await _tenant(client, db_session, monkeypatch, "auditcredits")
    from api.security.credit_packs import CREDIT_PACKS

    pack_id = CREDIT_PACKS[0]["id"]
    response = await client.post(f"/organizations/{org_id}/billing/credits/purchase", json={"pack_id": pack_id}, headers=headers)
    assert response.status_code == 200, response.text
    rows = await _rows(db_session, org_id)
    assert len(rows) == 1 and rows[0].action == "billing_credits_added" and '"paid": false' in rows[0].metadata_json


async def test_a_billing_country_change_is_audited(client, db_session, monkeypatch):
    headers, org_id, _u, _hb, _ob, _plans = await _tenant(client, db_session, monkeypatch, "auditcountry")
    response = await client.patch(f"/organizations/{org_id}/billing/country", json={"billing_country": "NG"}, headers=headers)
    assert response.status_code == 200, response.text
    rows = await _rows(db_session, org_id)
    assert len(rows) == 1 and rows[0].action == "billing_country_changed" and '"after": "NG"' in rows[0].metadata_json


async def test_each_organization_sees_only_its_own_billing_audit_rows(client, db_session, monkeypatch):
    headers_a, org_a, _u, headers_b, org_b, _plans = await _tenant(client, db_session, monkeypatch, "auditscope")
    await client.patch(f"/organizations/{org_a}/billing/country", json={"billing_country": "NG"}, headers=headers_a)
    await client.patch(f"/organizations/{org_b}/billing/country", json={"billing_country": "FR"}, headers=headers_b)
    for headers, org, other in ((headers_a, org_a, "FR"), (headers_b, org_b, "NG")):
        listing = await client.get(f"/organizations/{org}/audit-logs?action=billing_country_changed", headers=headers)
        assert listing.status_code == 200, listing.text
        assert "billing_country_changed" in listing.text and f'"after": "{other}"' not in listing.text.replace('\\"', '"')
