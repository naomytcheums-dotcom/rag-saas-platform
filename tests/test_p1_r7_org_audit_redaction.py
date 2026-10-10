"""R7: what an organization sees of the platform staff's actions in its own audit view.

The organization may see THAT a financial action happened on its account (and the before/after state), but not the staff member behind
it (id, IP address, user agent) nor the staff's internal notes: the payment reference of a manual settlement and the reason given for
a void or a cancellation. The platform-wide view keeps everything, and an organization member still sees its own actions in full.
"""

from api.config import settings
from api.models.billing import InvoiceStatus
from test_p0_billing_no_free_paid_plan import _auth
from test_p1_bill002_invoice_state_machine import _invoice, _world

REFERENCE = "WIRE-SECRET-REF-9917"
REASON = "chargeback fraud suspicion on this customer"
STAFF_AGENT = "StaffConsole/9.9 (internal)"


async def _staff_actions(client, db_session, register_payload, label):
    token, org_id, super_headers, _admin = await _world(client, db_session, register_payload, label)
    staff_headers = {**super_headers, "User-Agent": STAFF_AGENT, "X-Forwarded-For": "198.51.100.77"}
    paid = await _invoice(db_session, org_id, InvoiceStatus.pending)
    voided = await _invoice(db_session, org_id, InvoiceStatus.pending)
    assert (await client.post(f"/admin/organizations/{org_id}/invoices/{paid}/mark-paid", json={"reference": REFERENCE}, headers=staff_headers)).status_code == 200
    assert (await client.post(f"/admin/organizations/{org_id}/invoices/{voided}/void", json={"reason": REASON}, headers=staff_headers)).status_code == 200
    return token, org_id, super_headers


async def test_the_organization_view_hides_the_staff_identity_ip_agent_and_internal_notes(client, db_session, register_payload):
    token, org_id, _s = await _staff_actions(client, db_session, register_payload, "r7org")
    response = await client.get(f"/organizations/{org_id}/audit-logs?limit=100", headers=_auth(token))
    assert response.status_code == 200, response.text
    body = response.text
    for secret in (REFERENCE, REASON, STAFF_AGENT, "198.51.100.77"):
        assert secret not in body, f"{secret!r} must not reach the organization"
    items = {item["action"]: item for item in response.json()["items"]}
    assert {"invoice_marked_paid", "invoice_voided"} <= set(items), "the organization still sees that the actions happened"
    for action in ("invoice_marked_paid", "invoice_voided"):
        assert items[action]["user_id"] is None and items[action]["ip"] is None and items[action]["user_agent"] is None
        assert items[action]["metadata"]["before"] == "pending", "the before/after state stays visible"


async def test_the_platform_wide_view_keeps_everything(client, db_session, register_payload):
    _token, _org_id, super_headers = await _staff_actions(client, db_session, register_payload, "r7admin")
    response = await client.get("/admin/audit-logs?limit=100", headers=super_headers)
    assert response.status_code == 200, response.text
    assert REFERENCE in response.text and REASON in response.text and STAFF_AGENT in response.text


async def test_a_member_still_sees_its_own_reference_and_reason(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_ALLOW_SELF_SERVICE_PAID_PLANS", True)
    token, org_id, _s, _a = await _world(client, db_session, register_payload, "r7member")
    invoice_id = await _invoice(db_session, org_id, InvoiceStatus.pending)
    own = {"reference": "OWNER-REF-5521"}
    assert (await client.post(f"/organizations/{org_id}/billing/invoices/{invoice_id}/pay", json=own, headers=_auth(token))).status_code == 200
    response = await client.get(f"/organizations/{org_id}/audit-logs?action=invoice_marked_paid", headers=_auth(token))
    assert "OWNER-REF-5521" in response.text, "an organization's own action is not redacted"
    assert response.json()["items"][0]["user_id"] is not None
