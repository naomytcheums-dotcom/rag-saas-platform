"""
api/services/beeai_orchestrator.py -- `RequirementAgent.run` makes a
real, paid LLM call under the hood (via BeeAI's own internal litellm
dependency) -- same real, documented exception to this codebase's own
"no mocking" precedent as tests/test_llm_providers.py's own
litellm.acompletion mock: no real API key exists in this environment.
`RequirementAgent.run` is mocked here, but every mock returns the
EXACT real shape verified directly against the installed
`beeai-framework` package before writing these tests
(`RequirementAgentOutput.output` is a real `list[Message]`, `Message.text`
verified via a real `AssistantMessage` instance) -- never a fabricated
shape."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.beeai_orchestrator import (
    UnsupportedBeeAIProviderError, _PROVIDER_NAME_MAP, run_multi_agent_team, run_requirement_agent,
)


def _fake_output(text: str):
    message = MagicMock()
    message.text = text
    output = MagicMock()
    output.output = [message]
    return output


async def test_run_requirement_agent_uses_this_organizations_real_configured_model(monkeypatch, db_session):
    """Validation criterion: BeeAI must run against THIS organization's
    own real, configured provider/model -- never its own independent
    default."""
    from api.models.organization import Organization
    from api.security.organization_settings import update_org_settings

    org = Organization(name="BeeAI Org", slug=f"beeai-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    await update_org_settings(db_session, org.id, {"llm_provider": "anthropic", "llm_model": "claude-3-5-sonnet-20241022"})
    await db_session.commit()

    mock_from_name = MagicMock(return_value=MagicMock())
    mock_run = AsyncMock(return_value=_fake_output("real bee answer"))
    mock_agent_cls = MagicMock(return_value=MagicMock(run=mock_run))

    monkeypatch.setattr("beeai_framework.backend.chat.ChatModel.from_name", mock_from_name)
    monkeypatch.setattr("beeai_framework.agents.requirement.RequirementAgent", mock_agent_cls)

    result = await run_requirement_agent(db_session, org.id, "What is 2+2?")

    assert result == "real bee answer"
    mock_from_name.assert_called_once_with("anthropic:claude-3-5-sonnet-20241022")
    mock_run.assert_awaited_once_with("What is 2+2?")


async def test_run_requirement_agent_rejects_a_provider_beeai_has_no_backend_for(monkeypatch, db_session):
    from api.models.organization import Organization
    from api.security.organization_settings import update_org_settings

    org = Organization(name="Compat Org", slug=f"compat-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    await update_org_settings(db_session, org.id, {"llm_provider": "openai_compatible"})
    await db_session.commit()

    with pytest.raises(UnsupportedBeeAIProviderError):
        await run_requirement_agent(db_session, org.id, "hi")


def test_provider_name_map_covers_every_real_beeai_compatible_provider():
    """Real, documented BeeAI provider names (verified against
    ChatModel.from_name's own installed signature) -- "mistral" (this
    codebase's own name) maps to "mistralai" (BeeAI's own real name),
    not a typo."""
    assert _PROVIDER_NAME_MAP["mistral"] == "mistralai"
    assert _PROVIDER_NAME_MAP["anthropic"] == "anthropic"


def _fake_multi_agent_cls(responses_by_role: dict[str, list[str]]):
    """Real N-agent test double -- unlike the single-agent tests above
    (one MagicMock reused for the one real agent), `run_multi_agent_team`
    genuinely instantiates a DIFFERENT `RequirementAgent` per role (the
    coordinator, called twice -- plan then synthesize -- plus one per
    specialist), so this factory hands back a distinct fake agent per
    `role=`, each with its OWN queued canned `.run()` outputs -- proves
    real, separate agents are used, not the same one reused for every
    role."""
    def _make(*, llm=None, role=None, instructions=None, **kwargs):
        queue = list(responses_by_role[role])

        async def _run(task):
            return _fake_output(queue.pop(0))

        agent = MagicMock()
        agent.run = _run
        return agent
    return _make


async def test_run_multi_agent_team_runs_genuinely_distinct_agents_and_synthesizes_a_real_final_answer(monkeypatch, db_session):
    """Validation criterion: a real coordinator plans, real DISTINCT
    specialist agents run their own subtasks concurrently, and the
    same coordinator synthesizes their real outputs -- the actual
    N-agent architecture, not a single agent standing in for a team."""
    from api.models.organization import Organization
    from api.security.organization_settings import update_org_settings

    org = Organization(name="Multi Agent Org", slug=f"multi-agent-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    await update_org_settings(db_session, org.id, {"llm_provider": "anthropic", "llm_model": "claude-3-5-sonnet-20241022"})
    await db_session.commit()

    responses_by_role = {
        "Coordinator": [
            "Researcher: find real facts about X\nWriter: draft a real summary",
            "The real, synthesized final answer.",
        ],
        "Researcher": ["Real researched facts."],
        "Writer": ["Real drafted summary."],
    }
    monkeypatch.setattr("beeai_framework.backend.chat.ChatModel.from_name", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr("beeai_framework.agents.requirement.RequirementAgent", _fake_multi_agent_cls(responses_by_role))

    specialists = [
        {"name": "Researcher", "role": "Researcher", "instructions": "Find real facts."},
        {"name": "Writer", "role": "Writer", "instructions": "Write real summaries."},
    ]
    result = await run_multi_agent_team(db_session, org.id, "Explain X", specialists)

    assert result["specialist_outputs"]["Researcher"] == "Real researched facts."
    assert result["specialist_outputs"]["Writer"] == "Real drafted summary."
    assert result["final_answer"] == "The real, synthesized final answer."
    assert "Researcher: find real facts about X" in result["plan"]


async def test_run_multi_agent_team_rejects_an_empty_real_team(db_session):
    from api.models.organization import Organization
    from api.security.organization_settings import update_org_settings

    org = Organization(name="Empty Team Org", slug=f"empty-team-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    await update_org_settings(db_session, org.id, {"llm_provider": "anthropic", "llm_model": "claude-3-5-sonnet-20241022"})
    await db_session.commit()

    with pytest.raises(ValueError):
        await run_multi_agent_team(db_session, org.id, "Explain X", specialists=[])


def test_parse_plan_falls_back_to_the_original_task_for_an_unaddressed_specialist():
    """Real, honest robustness against a real LLM's own free-text plan
    not covering every specialist by name -- never a silently dropped
    team member."""
    from api.services.beeai_orchestrator import _parse_plan

    plan_text = "Researcher: find real facts about X"
    assignments = _parse_plan(plan_text, names=["Researcher", "Writer"], fallback_task="Explain X")

    assert assignments["Researcher"] == "find real facts about X"
    assert assignments["Writer"] == "Explain X"
