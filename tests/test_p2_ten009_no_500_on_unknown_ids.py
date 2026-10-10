"""TEN-009 regression guard (the 500s of the audit no longer reproduce, so this is NOT a failing-before test): unknown ids and an
unconfigured Airbyte answer with an explicit 4xx/501 instead of a 500."""

import uuid

import pytest

from test_billing_credit_packs import _auth_header, _register_and_create_org


@pytest.mark.parametrize("route", ["subscribe", "upgrade", "downgrade"])
@pytest.mark.parametrize("period", ["monthly", "yearly"])
async def test_changing_to_an_unknown_plan_is_a_404_not_a_500(client, register_payload, route, period):
    token, org_id = await _register_and_create_org(client, register_payload)

    response = await client.post(f"/organizations/{org_id}/billing/{route}", json={"plan_id": str(uuid.uuid4()), "billing_period": period}, headers=_auth_header(token))

    assert response.status_code == 404 and response.json()["detail"] == "Plan not found"


async def test_unknown_questions_and_messages_are_404s(client, register_payload):
    token, _org_id = await _register_and_create_org(client, register_payload)
    headers = _auth_header(token)
    missing = uuid.uuid4()

    statuses = [
        (await client.post(f"/questions/{missing}/run", json={"agent_id": str(missing)}, headers=headers)).status_code,
        (await client.post(f"/questions/{missing}/latency", json={"agent_id": str(missing)}, headers=headers)).status_code,
        (await client.post(f"/messages/{missing}/follow-up", json={}, headers=headers)).status_code,
        (await client.get(f"/messages/{missing}/follow-up", headers=headers)).status_code,
    ]

    assert statuses == [404, 404, 404, 404]


async def test_an_unconfigured_airbyte_is_a_501(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    headers = _auth_header(token)
    base = f"/organizations/{org_id}/integrations/airbyte"

    responses = [
        await client.get(f"{base}/source-definitions", headers=headers),
        await client.post(f"{base}/sources", json={"name": "x", "source_definition_id": "y", "connection_configuration": {}}, headers=headers),
        await client.get(f"{base}/sources/abc/catalog", headers=headers),
    ]

    assert [r.status_code for r in responses] == [501, 501, 501]
