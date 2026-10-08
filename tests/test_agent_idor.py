"""P2C-2: foreign persisted agent CRUD/configuration and API-key execution."""

from unittest.mock import AsyncMock

from api.models.agent import Agent
from test_document_idor import denied, make_key, make_tenants, snapshot


async def test_agent_idor(client, db_session, monkeypatch):
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    (owner, org_a, _), (attacker, org_b, _) = await make_tenants(
        client, db_session, monkeypatch, "agent"
    )
    agent = Agent(
        organization_id=org_a,
        name="private-agent",
        system_prompt="private-system-prompt",
        model_config_json={},
    )
    db_session.add(agent)
    await db_session.commit()
    baseline = await snapshot(db_session, agent)
    provider = AsyncMock()
    retrieval = AsyncMock()
    monkeypatch.setattr("litellm.acompletion", provider)
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", retrieval)
    control = await client.get(f"/agents/{agent.id}", headers=owner)
    assert control.status_code == 200, control.text
    violations = []
    for suffix in ("", "/model", "/tools", "/memory-config", "/permissions", "/guardrails"):
        await denied(client, "GET", f"/agents/{agent.id}{suffix}", attacker, violations)
    await denied(
        client, "PATCH", f"/agents/{agent.id}", attacker, violations,
        json={"name": "attacker-rename"},
    )
    for action in ("activate", "pause", "archive", "memory/clear"):
        await denied(client, "POST", f"/agents/{agent.id}/{action}", attacker, violations)
    await denied(client, "DELETE", f"/agents/{agent.id}", attacker, violations)
    key = await make_key(client, attacker, org_b, ["chat:write", "agents:run"])
    for path, payload in (
        ("/v1/chat", {"message": "Hi", "agent_id": str(agent.id)}),
        ("/v1/agents/run", {"input": "Hi", "agent_id": str(agent.id)}),
    ):
        response = await denied(
            client, "POST", path, key, violations, expected=(400,), json=payload
        )
        if "Agent not found" not in response.text:
            violations.append(f"{path}: missing resource-denial detail")
    assert await snapshot(db_session, agent) == baseline
    provider.assert_not_called()
    retrieval.assert_not_called()
    assert not violations, "\n".join(violations)
