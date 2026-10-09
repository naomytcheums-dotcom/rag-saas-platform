"""BILL-002 / V1: invoices follow a state machine and only the platform settles them.

Before: any owner/admin of an organization could void its own invoices, even after they were paid (the audit's runtime run answered 200),
and `pay` could be repeated and re-applied to void invoices. Now: paid and void are terminal, `void` and `pay` are superadmin acts
(back-office routes under /admin/organizations/{org}/invoices/...), and each change is audited with before/after.
"""

import uuid

from sqlalchemy import select

from api.config import settings
from api.models.audit_log import AuditLog
from api.models.billing import Invoice, InvoiceStatus
from api.models.user import User, UserRole
from api.services.billing_invoices import create_invoice
from test_p0_billing_no_free_paid_plan import _auth, _org
from test_p1_backoffice_and_suspension import _bearer, _platform_user


async def _invoice(db_session, org_id, status=InvoiceStatus.pending):
    invoice = await create_invoice(db_session, org_id, lines=[{"description": "Pro plan", "quantity": 1, "unit_price_cents": 19900}])
    invoice.status = status
    if status == InvoiceStatus.paid:
        invoice.paid_at = invoice.created_at
    await db_session.commit()
    return invoice.id


async def _state(db_session, invoice_id):
    db_session.expire_all()
    invoice = await db_session.get(Invoice, invoice_id)
    return invoice.status, invoice.paid_at, invoice.voided_at


async def _audits(db_session, action):
    db_session.expire_all()
    return list((await db_session.scalars(select(AuditLog).where(AuditLog.action == action))).all())


async def _world(client, db_session, register_payload, label):
    token, org_id = await _org(client, register_payload)
    superadmin = await _platform_user(db_session, f"super-{label}@example.com", UserRole.superadmin)
    admin = await _platform_user(db_session, f"admin-{label}@example.com", UserRole.admin)
    return token, org_id, _bearer(superadmin.id), _bearer(admin.id)


async def test_an_organization_owner_cannot_void_its_own_invoice(client, db_session, register_payload):
    token, org_id, _s, _a = await _world(client, db_session, register_payload, "ownervoid")
    invoice_id = await _invoice(db_session, org_id)
    response = await client.post(f"/organizations/{org_id}/billing/invoices/{invoice_id}/void", json={"reason": "cancel my debt"}, headers=_auth(token))
    assert response.status_code == 403
    assert (await _state(db_session, invoice_id))[0] == InvoiceStatus.pending
    assert await _audits(db_session, "invoice_voided") == []


async def test_a_superadmin_voids_an_unpaid_invoice_without_being_a_member_and_it_is_audited(client, db_session, register_payload):
    _token, org_id, super_h, _a = await _world(client, db_session, register_payload, "superVoid")
    invoice_id = await _invoice(db_session, org_id)
    response = await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/void", json={"reason": "issued by mistake"}, headers=super_h)
    assert response.status_code == 200, response.text
    status_after, _paid_at, voided_at = await _state(db_session, invoice_id)
    assert status_after == InvoiceStatus.void and voided_at is not None
    rows = await _audits(db_session, "invoice_voided")
    assert len(rows) == 1 and rows[0].organization_id == org_id
    assert '"before": "pending"' in rows[0].metadata_json and '"after": "void"' in rows[0].metadata_json


async def test_a_paid_invoice_can_never_be_voided(client, db_session, register_payload):
    _token, org_id, super_h, _a = await _world(client, db_session, register_payload, "paidvoid")
    invoice_id = await _invoice(db_session, org_id, InvoiceStatus.paid)
    before = await _state(db_session, invoice_id)
    response = await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/void", json={"reason": "x"}, headers=super_h)
    assert response.status_code == 409
    assert await _state(db_session, invoice_id) == before
    assert await _audits(db_session, "invoice_voided") == []


async def test_a_void_invoice_cannot_be_paid(client, db_session, register_payload):
    _token, org_id, super_h, _a = await _world(client, db_session, register_payload, "voidpay")
    invoice_id = await _invoice(db_session, org_id, InvoiceStatus.void)
    response = await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/mark-paid", headers=super_h)
    assert response.status_code == 409
    assert (await _state(db_session, invoice_id))[0] == InvoiceStatus.void


async def test_marking_paid_twice_keeps_the_first_payment_date_and_audits_once(client, db_session, register_payload):
    _token, org_id, super_h, _a = await _world(client, db_session, register_payload, "paytwice")
    invoice_id = await _invoice(db_session, org_id)
    first = await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/mark-paid", headers=super_h)
    paid_at = (await _state(db_session, invoice_id))[1]
    second = await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/mark-paid", headers=super_h)
    assert (first.status_code, second.status_code) == (200, 200)
    assert (await _state(db_session, invoice_id))[1] == paid_at
    assert len(await _audits(db_session, "invoice_marked_paid")) == 1


async def test_voiding_twice_is_idempotent(client, db_session, register_payload):
    _token, org_id, super_h, _a = await _world(client, db_session, register_payload, "voidtwice")
    invoice_id = await _invoice(db_session, org_id)
    for _ in range(2):
        assert (await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/void", json={"reason": "dup"}, headers=super_h)).status_code == 200
    assert len(await _audits(db_session, "invoice_voided")) == 1


async def test_a_plain_platform_admin_cannot_settle_invoices(client, db_session, register_payload):
    _token, org_id, _s, admin_h = await _world(client, db_session, register_payload, "adminsettle")
    invoice_id = await _invoice(db_session, org_id)
    for path, body in ((f"/admin/organizations/{org_id}/invoices/{invoice_id}/mark-paid", None), (f"/admin/organizations/{org_id}/invoices/{invoice_id}/void", {"reason": "x"})):
        assert (await client.post(path, json=body, headers=admin_h)).status_code == 403
    assert (await _state(db_session, invoice_id))[0] == InvoiceStatus.pending


async def test_anonymous_and_other_organizations_are_refused(client, db_session, register_payload):
    token, org_id, super_h, _a = await _world(client, db_session, register_payload, "scope")
    invoice_id = await _invoice(db_session, org_id)
    other_org = uuid.uuid4()
    assert (await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/void", json={"reason": "x"})).status_code in (401, 403)
    assert (await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/void", json={"reason": "x"}, headers=_auth(token))).status_code == 403
    wrong_scope = await client.post(f"/admin/organizations/{other_org}/invoices/{invoice_id}/mark-paid", headers=super_h)
    assert wrong_scope.status_code == 404, "an invoice is only reachable through its own organization"
    assert (await _state(db_session, invoice_id))[0] == InvoiceStatus.pending


async def test_a_superadmin_who_is_also_a_member_may_use_the_organization_routes(client, db_session, register_payload):
    token, org_id, _s, _a = await _world(client, db_session, register_payload, "membersuper")
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.superadmin
    await db_session.commit()
    invoice_id = await _invoice(db_session, org_id)
    assert (await client.post(f"/organizations/{org_id}/billing/invoices/{invoice_id}/void", json={"reason": "x"}, headers=_auth(token))).status_code == 200


async def test_the_self_hosted_opt_in_still_applies_the_state_machine(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_ALLOW_SELF_SERVICE_PAID_PLANS", True)
    token, org_id, _s, _a = await _world(client, db_session, register_payload, "optin")
    pending = await _invoice(db_session, org_id)
    paid = await _invoice(db_session, org_id, InvoiceStatus.paid)
    assert (await client.post(f"/organizations/{org_id}/billing/invoices/{pending}/void", json={"reason": "x"}, headers=_auth(token))).status_code == 200
    assert (await client.post(f"/organizations/{org_id}/billing/invoices/{paid}/void", json={"reason": "x"}, headers=_auth(token))).status_code == 409
    assert (await _state(db_session, paid))[0] == InvoiceStatus.paid
