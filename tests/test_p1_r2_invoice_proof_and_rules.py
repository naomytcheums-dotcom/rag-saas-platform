"""R2 and the invoice rules decided by the product owner.

- Marking an invoice paid by hand needs a payment reference whenever a superadmin does it, on the platform route AND on the organization
  route (422 otherwise, invoice unchanged). Under the self-hosted opt-in (BILLING_ALLOW_SELF_SERVICE_PAID_PLANS) the reference stays
  optional but the audit row says `self_service: true`.
- draft -> paid is refused (an invoice never issued is not settled); pending/sent/overdue -> paid is allowed.
- Voiding needs a reason (422 otherwise); draft/pending/sent/overdue -> void is allowed, paid -> void and void -> paid stay 409.
- Provider-confirmed payments keep their own chain (signature + idempotence) and are not concerned.
"""

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.billing import Invoice, InvoiceStatus
from api.models.user import User, UserRole
from test_p0_billing_no_free_paid_plan import _auth
from test_p1_bill002_invoice_state_machine import _audits, _invoice, _state, _world

PROOF = {"reference": "WIRE-2026-0042"}


async def _member_superadmin(client, db_session, register_payload, label):
    token, org_id, super_headers, _admin = await _world(client, db_session, register_payload, label)
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.superadmin
    await db_session.commit()
    return token, org_id, super_headers


# ------------------------------------------------------------ the payment reference


@pytest.mark.parametrize("body", [None, {}, {"reference": ""}, {"reference": "  "}, {"reference": "ab"}])
async def test_a_superadmin_member_cannot_mark_an_invoice_paid_without_a_reference(client, db_session, register_payload, body):
    token, org_id, _s = await _member_superadmin(client, db_session, register_payload, "r2noref")
    invoice_id = await _invoice(db_session, org_id)
    response = await client.post(f"/organizations/{org_id}/billing/invoices/{invoice_id}/pay", json=body, headers=_auth(token))
    assert response.status_code == 422, (body, response.text)
    assert (await _state(db_session, invoice_id))[0] == InvoiceStatus.pending
    assert await _audits(db_session, "invoice_marked_paid") == []


async def test_a_superadmin_member_with_a_reference_marks_it_paid_and_the_audit_keeps_the_reference(client, db_session, register_payload):
    token, org_id, _s = await _member_superadmin(client, db_session, register_payload, "r2ref")
    invoice_id = await _invoice(db_session, org_id)
    response = await client.post(f"/organizations/{org_id}/billing/invoices/{invoice_id}/pay", json=PROOF, headers=_auth(token))
    assert response.status_code == 200, response.text
    rows = await _audits(db_session, "invoice_marked_paid")
    assert len(rows) == 1 and "WIRE-2026-0042" in rows[0].metadata_json and "self_service" not in rows[0].metadata_json


async def test_the_platform_route_also_refuses_a_blank_reference(client, db_session, register_payload):
    _token, org_id, super_headers, _a = await _world(client, db_session, register_payload, "r2blank")
    invoice_id = await _invoice(db_session, org_id)
    for body in ({"reference": "   "}, {"reference": None}):
        assert (await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/mark-paid", json=body, headers=super_headers)).status_code == 422
    assert (await _state(db_session, invoice_id))[0] == InvoiceStatus.pending


async def test_under_the_self_hosted_opt_in_the_reference_is_optional_but_the_audit_says_self_service(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_ALLOW_SELF_SERVICE_PAID_PLANS", True)
    token, org_id, _s, _a = await _world(client, db_session, register_payload, "r2selfhost")
    invoice_id = await _invoice(db_session, org_id)
    response = await client.post(f"/organizations/{org_id}/billing/invoices/{invoice_id}/pay", headers=_auth(token))
    assert response.status_code == 200, response.text
    rows = await _audits(db_session, "invoice_marked_paid")
    assert len(rows) == 1 and '"self_service": true' in rows[0].metadata_json


async def test_without_the_opt_in_an_owner_is_still_refused(client, db_session, register_payload):
    token, org_id, _s, _a = await _world(client, db_session, register_payload, "r2owner")
    invoice_id = await _invoice(db_session, org_id)
    assert (await client.post(f"/organizations/{org_id}/billing/invoices/{invoice_id}/pay", json=PROOF, headers=_auth(token))).status_code == 403
    assert (await _state(db_session, invoice_id))[0] == InvoiceStatus.pending


# ------------------------------------------------------------ draft / pending / sent / overdue


async def test_a_draft_invoice_cannot_be_marked_paid(client, db_session, register_payload):
    _token, org_id, super_headers, _a = await _world(client, db_session, register_payload, "r2draft")
    invoice_id = await _invoice(db_session, org_id, InvoiceStatus.draft)
    response = await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/mark-paid", json=PROOF, headers=super_headers)
    assert response.status_code == 409 and "draft" in response.json()["detail"]
    assert (await _state(db_session, invoice_id))[0] == InvoiceStatus.draft
    assert await _audits(db_session, "invoice_marked_paid") == []


@pytest.mark.parametrize("status", [InvoiceStatus.pending, InvoiceStatus.sent, InvoiceStatus.overdue])
async def test_an_issued_invoice_can_be_marked_paid_with_a_reference(client, db_session, register_payload, status):
    _token, org_id, super_headers, _a = await _world(client, db_session, register_payload, f"r2pay{status.value}")
    invoice_id = await _invoice(db_session, org_id, status)
    response = await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/mark-paid", json=PROOF, headers=super_headers)
    assert response.status_code == 200, response.text
    assert (await _state(db_session, invoice_id))[0] == InvoiceStatus.paid


# ------------------------------------------------------------ voiding needs a reason


@pytest.mark.parametrize("body", [None, {}, {"reason": ""}, {"reason": "   "}, {"reason": None}])
async def test_voiding_without_a_reason_is_refused_on_both_routes(client, db_session, register_payload, body):
    token, org_id, super_headers = await _member_superadmin(client, db_session, register_payload, "r2noreason")
    invoice_id = await _invoice(db_session, org_id)
    assert (await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/void", json=body, headers=super_headers)).status_code == 422
    assert (await client.post(f"/organizations/{org_id}/billing/invoices/{invoice_id}/void", json=body, headers=_auth(token))).status_code == 422
    assert (await _state(db_session, invoice_id))[0] == InvoiceStatus.pending
    assert await _audits(db_session, "invoice_voided") == []


@pytest.mark.parametrize("status", [InvoiceStatus.draft, InvoiceStatus.pending, InvoiceStatus.sent, InvoiceStatus.overdue])
async def test_an_unpaid_invoice_can_be_voided_with_a_reason_and_the_reason_is_audited(client, db_session, register_payload, status):
    _token, org_id, super_headers, _a = await _world(client, db_session, register_payload, f"r2void{status.value}")
    invoice_id = await _invoice(db_session, org_id, status)
    response = await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/void", json={"reason": "issued twice by mistake"}, headers=super_headers)
    assert response.status_code == 200, response.text
    rows = await _audits(db_session, "invoice_voided")
    assert len(rows) == 1 and "issued twice by mistake" in rows[0].metadata_json


async def test_paid_and_void_stay_terminal(client, db_session, register_payload):
    _token, org_id, super_headers, _a = await _world(client, db_session, register_payload, "r2terminal")
    paid = await _invoice(db_session, org_id, InvoiceStatus.paid)
    voided = await _invoice(db_session, org_id, InvoiceStatus.void)
    assert (await client.post(f"/admin/organizations/{org_id}/invoices/{paid}/void", json={"reason": "no"}, headers=super_headers)).status_code == 409
    assert (await client.post(f"/admin/organizations/{org_id}/invoices/{voided}/mark-paid", json=PROOF, headers=super_headers)).status_code == 409
    assert (await _state(db_session, paid))[0] == InvoiceStatus.paid and (await _state(db_session, voided))[0] == InvoiceStatus.void


async def test_the_invoice_table_is_untouched_by_a_refused_attempt(client, db_session, register_payload):
    _token, org_id, super_headers, _a = await _world(client, db_session, register_payload, "r2untouched")
    invoice_id = await _invoice(db_session, org_id, InvoiceStatus.draft)
    before = await db_session.scalar(select(Invoice.updated_at).where(Invoice.id == invoice_id))
    await client.post(f"/admin/organizations/{org_id}/invoices/{invoice_id}/mark-paid", json=PROOF, headers=super_headers)
    db_session.expire_all()
    assert await db_session.scalar(select(Invoice.updated_at).where(Invoice.id == invoice_id)) == before
