"""P2C-9: persisted foreign billing rows and mocked Stripe ownership boundary."""

from unittest.mock import AsyncMock, Mock

from sqlalchemy import select

from api.models.billing import (
    Credit,
    CreditTransaction,
    CreditTransactionType,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    PaymentCustomer,
    PaymentProvider,
    UsageAlert,
)
from test_document_idor import denied, make_tenants, snapshot


async def test_billing_idor(client, db_session, monkeypatch):
    (owner, org_a, user_a), (attacker, org_b, _) = await make_tenants(
        client, db_session, monkeypatch, "billing"
    )
    invoice = Invoice(
        organization_id=org_a, number="P2C-PRIVATE-INVOICE", status=InvoiceStatus.pending,
        subtotal_cents=100, total_cents=100,
    )
    credit = await db_session.scalar(select(Credit).where(Credit.organization_id == org_a))
    if credit is None:
        credit = Credit(organization_id=org_a, balance=1000)
        db_session.add(credit)
    else:
        credit.balance = 1000
    transaction = CreditTransaction(
        organization_id=org_a, type=CreditTransactionType.grant,
        amount=1000, balance_after=1000, reason="private-credit", user_id=user_a,
    )
    alert = UsageAlert(
        organization_id=org_a, resource_type="tokens", threshold_percent=80, created_by=user_a
    )
    customer_a = PaymentCustomer(
        organization_id=org_a, provider=PaymentProvider.stripe,
        external_customer_id="cus_p2c_a",
    )
    customer_b = PaymentCustomer(
        organization_id=org_b, provider=PaymentProvider.stripe,
        external_customer_id="cus_p2c_b",
    )
    db_session.add_all([invoice, transaction, alert, customer_a, customer_b])
    await db_session.flush()
    line = InvoiceLine(
        invoice_id=invoice.id, description="private-line",
        quantity=1, unit_price_cents=100, total_cents=100,
    )
    db_session.add(line)
    await db_session.commit()
    invoice_id, alert_id = invoice.id, alert.id
    protected = (invoice, line, credit, transaction, alert, customer_a, customer_b)
    baseline = await snapshot(db_session, *protected)
    email, reminder = AsyncMock(), AsyncMock()
    monkeypatch.setattr("api.services.email_branding.send_branded_invoice_email", email)
    monkeypatch.setattr("api.services.email_branding.send_branded_invoice_reminder_email", reminder)
    # Payment methods have no local ORM table; their customer association is
    # a provider fixture tied to the two real SQLite PaymentCustomer rows.
    foreign_method = {
        "id": "pm_p2c_a", "customer": "cus_p2c_a",
        "card": {"brand": "visa", "last4": "4242", "exp_month": 1, "exp_year": 2030},
    }
    stripe = Mock()
    stripe.PaymentMethod.retrieve.return_value = foreign_method
    stripe.PaymentMethod.list.side_effect = lambda **kwargs: {
        "data": [foreign_method] if kwargs["customer"] == "cus_p2c_a" else []
    }
    monkeypatch.setattr("api.services.billing_stripe._client", Mock(return_value=stripe))
    control = await client.get(
        f"/organizations/{org_a}/billing/invoices/{invoice_id}", headers=owner
    )
    assert control.status_code == 200, control.text
    control = await client.get(
        f"/organizations/{org_a}/billing/stripe/payment-methods", headers=owner
    )
    assert control.status_code == 200
    assert control.json()[0]["id"] == foreign_method["id"]
    violations = []
    for suffix in ("/credits", "/credits/transactions", "/invoices", "/usage/alerts"):
        await denied(
            client, "GET", f"/organizations/{org_a}/billing{suffix}", attacker, violations
        )
    for path_org in (org_a, org_b):
        root = f"/organizations/{path_org}/billing/invoices/{invoice_id}"
        await denied(client, "GET", root, attacker, violations)
        await denied(client, "GET", root + "/pdf", attacker, violations)
        for action in ("send", "remind", "pay", "void"):
            await denied(
                client, "POST", root + "/" + action, attacker, violations,
                json={"reason": "attacker-void"} if action == "void" else {},
            )
        await denied(
            client, "DELETE", f"/organizations/{path_org}/billing/usage/alerts/{alert_id}",
            attacker, violations,
        )
    await denied(
        client, "DELETE",
        f"/organizations/{org_a}/billing/stripe/payment-methods/{foreign_method['id']}",
        attacker, violations,
    )
    await denied(
        client, "DELETE",
        f"/organizations/{org_b}/billing/stripe/payment-methods/{foreign_method['id']}",
        attacker, violations,
    )
    assert await snapshot(db_session, *protected) == baseline
    email.assert_not_called()
    reminder.assert_not_called()
    if stripe.PaymentMethod.detach.called:
        violations.append("CONFIRMED: foreign payment-method ID reached mocked Stripe.detach")
    assert not violations, "\n".join(violations)
