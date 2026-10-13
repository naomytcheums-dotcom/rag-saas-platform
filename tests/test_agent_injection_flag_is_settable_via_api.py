"""E2E finding 2026-10-12: `prompt_injection_detection_enabled` existed on the Agent model and in the guardrail logic, but no request schema accepted it, so
`PATCH /agents/{id}` answered 200 and silently ignored it: customers could not turn the detector on (only the Factory could). A planted secret then leaked
through /v1/chat with the 'detector on' setting the customer believed was active."""

from sqlalchemy import select

from api.models.user import User


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _owner_and_org(client, db_session, register_payload):
    token = (await client.post("/auth/register", json={**register_payload, "accept_terms": True})).json()["access_token"]
    org = (await client.post("/organizations", json={"name": "Acme"}, headers=_auth(token))).json()
    assert await db_session.scalar(select(User).where(User.email == register_payload["email"])) is not None
    return token, org["id"]


async def test_an_agent_can_be_created_with_the_detector_on(client, db_session, register_payload):
    token, org_id = await _owner_and_org(client, db_session, register_payload)

    response = await client.post(f"/organizations/{org_id}/agents", json={"name": "Bot", "prompt_injection_detection_enabled": True}, headers=_auth(token))

    assert response.status_code in (200, 201), response.text
    assert response.json()["prompt_injection_detection_enabled"] is True


async def test_the_detector_can_be_switched_on_and_off_with_patch_agent(client, db_session, register_payload):
    token, org_id = await _owner_and_org(client, db_session, register_payload)
    agent_id = (await client.post(f"/organizations/{org_id}/agents", json={"name": "Bot"}, headers=_auth(token))).json()["id"]

    on = await client.patch(f"/agents/{agent_id}", json={"prompt_injection_detection_enabled": True}, headers=_auth(token))
    shown = await client.get(f"/agents/{agent_id}", headers=_auth(token))
    off = await client.patch(f"/agents/{agent_id}", json={"prompt_injection_detection_enabled": False}, headers=_auth(token))

    assert on.status_code == 200 and on.json()["prompt_injection_detection_enabled"] is True
    assert shown.json()["prompt_injection_detection_enabled"] is True
    assert off.json()["prompt_injection_detection_enabled"] is False


async def test_the_guardrails_endpoint_reads_and_writes_the_flag(client, db_session, register_payload):
    token, org_id = await _owner_and_org(client, db_session, register_payload)
    agent_id = (await client.post(f"/organizations/{org_id}/agents", json={"name": "Bot"}, headers=_auth(token))).json()["id"]

    before = await client.get(f"/agents/{agent_id}/guardrails", headers=_auth(token))
    patched = await client.patch(f"/agents/{agent_id}/guardrails", json={"prompt_injection_detection_enabled": True}, headers=_auth(token))
    after = await client.get(f"/agents/{agent_id}/guardrails", headers=_auth(token))

    assert before.json()["prompt_injection_detection_enabled"] is False
    assert patched.status_code == 200 and patched.json()["prompt_injection_detection_enabled"] is True
    assert after.json()["prompt_injection_detection_enabled"] is True
