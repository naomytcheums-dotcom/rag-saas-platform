"""P2C-8: an API key cannot address another existing organization's A2A API."""

from unittest.mock import AsyncMock

from sqlalchemy import func, select

from api.models.billing import Credit, CreditTransaction
from api.models.organization import Organization
from test_document_idor import denied, make_key, make_tenants, snapshot


async def test_a2a_idor(client, db_session, monkeypatch):
    (owner, org_a, _), (attacker, org_b, _) = await make_tenants(
        client, db_session, monkeypatch, "a2a"
    )
    organizations = [
        await db_session.get(Organization, org_a),
        await db_session.get(Organization, org_b),
    ]
    credits = []
    for org_id in (org_a, org_b):
        credit = await db_session.scalar(select(Credit).where(Credit.organization_id == org_id))
        if credit is None:
            credit = Credit(organization_id=org_id, balance=1000)
            db_session.add(credit)
        else:
            credit.balance = 1000
        credits.append(credit)
    await db_session.commit()
    key_a = await make_key(client, owner, org_a, ["a2a:call"])
    key_b = await make_key(client, attacker, org_b, ["a2a:call"])
    baseline = await snapshot(db_session, *organizations, *credits)
    transactions = await db_session.scalar(select(func.count()).select_from(CreditTransaction))
    rate_limit, preflight, debit, executor = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr("api.routers.a2a.enforce_rate_limit", rate_limit)
    monkeypatch.setattr("api.routers.a2a.assert_org_can_spend", preflight)
    monkeypatch.setattr("api.routers.a2a.deduct_credits", debit)
    monkeypatch.setattr("api.routers.a2a._BilledRagAgentExecutor.execute", executor)
    control = await client.get(
        f"/a2a/{org_a}/.well-known/agent-card.json", headers=key_a
    )
    assert control.status_code == 200, control.text
    violations = []
    for target_org, foreign_key in ((org_a, key_b), (org_b, key_a)):
        await denied(
            client, "GET", f"/a2a/{target_org}/.well-known/agent-card.json",
            foreign_key, violations,
        )
        await denied(
            client, "POST", f"/a2a/{target_org}",
            {**foreign_key, "A2A-Version": "1.0"}, violations,
            json={
                "jsonrpc": "2.0", "id": "p2c-local", "method": "SendMessage",
                "params": {"message": {
                    "messageId": "p2c-message", "role": "ROLE_USER",
                    "parts": [{"text": "No provider should receive this"}],
                }},
            },
        )
    assert await snapshot(db_session, *organizations, *credits) == baseline
    assert await db_session.scalar(select(func.count()).select_from(CreditTransaction)) == transactions
    for boundary in (rate_limit, preflight, debit, executor):
        boundary.assert_not_called()
    assert not violations, "\n".join(violations)
