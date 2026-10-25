"""api/tasks/autonomous_agents.py: the Celery jobs around autonomous agents.

The memory sweeps run the real service functions (consolidate_memory, forget_old_memory) on the test database, with only the LLM
replaced; the guardrail sweep marks real stuck agents. `_session_factory` is pointed at the test session, as in tests/test_media_tasks.py.
"""

import datetime as dt
import logging
import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.autonomous_agent import AgentMemory, AgentPlan, AutonomousAgent, AutonomousAgentStatus
from api.models.user import User
from api.services.llm_providers import LLMError
from api.tasks import autonomous_agents as agent_tasks

LONG_AGO = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)


@pytest.fixture
async def org_id(client, db_session):
    email = f"agent-tasks-{uuid.uuid4().hex[:8]}@example.com"
    token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    org = (await client.post("/organizations", json={"name": "Agent tasks"}, headers={"Authorization": f"Bearer {token}"})).json()
    assert await db_session.scalar(select(User).where(User.email == email)) is not None
    return uuid.UUID(org["id"])


@pytest.fixture
def task_session(monkeypatch, db_session):
    disposed = []

    class _Engine:
        async def dispose(self):
            disposed.append(True)

    @asynccontextmanager
    async def _session():
        yield db_session

    monkeypatch.setattr(agent_tasks, "_session_factory", lambda: (_Engine(), _session))
    monkeypatch.setattr(settings, "AUTONOMOUS_MEMORY_ENABLED", False)  # no embedding call when a memory is stored
    return disposed


async def _agent(db_session, org_id, name, **fields):
    agent = AutonomousAgent(organization_id=org_id, name=name, goal=f"goal of {name}", **fields)
    db_session.add(agent)
    await db_session.commit()
    return agent


def _memory(agent, kind, content, created_at=None):
    fields = {"created_at": created_at} if created_at else {}
    return AgentMemory(agent_id=agent.id, memory_type=kind, content=content, **fields)


async def _memories(db_session, agent_id):
    await db_session.rollback()  # only what the sweep committed is visible (and every loaded object is expired)
    rows = (await db_session.scalars(select(AgentMemory).where(AgentMemory.agent_id == agent_id))).all()
    return sorted((m.memory_type, m.content) for m in rows)


async def test_consolidation_folds_short_term_memories_into_one_long_term_summary(db_session, org_id, task_session, monkeypatch, caplog):
    busy = await _agent(db_session, org_id, "busy")
    quiet = await _agent(db_session, org_id, "quiet")
    broken = await _agent(db_session, org_id, "broken")
    llm_down = await _agent(db_session, org_id, "llm-down")
    db_session.add_all([
        _memory(busy, "short_term", "customer asked for a refund"), _memory(busy, "short_term", "refund approved"),
        _memory(busy, "episodic", "first contact"),
        _memory(quiet, "short_term", "only one event"),
        _memory(broken, "short_term", "a"), _memory(broken, "short_term", "b"),
        _memory(llm_down, "short_term", "x"), _memory(llm_down, "short_term", "y"),
    ])
    await db_session.commit()
    ids = {"busy": busy.id, "quiet": quiet.id, "llm_down": llm_down.id}
    broken_id = broken.id
    prompts = []

    async def fake_llm(messages):
        prompt = messages[0]["content"]
        prompts.append(prompt)
        if "- a\n- b" in prompt:
            raise RuntimeError("provider exploded")
        if "- x\n- y" in prompt:
            raise LLMError("rate limited")
        return "The refund was requested and approved."

    monkeypatch.setattr("api.services.autonomous_agents.chat_completion", fake_llm)

    with caplog.at_level(logging.WARNING, logger="api.tasks.autonomous_agents"):
        assert await agent_tasks._consolidate_agent_memory_async() == 1

    assert any("- customer asked for a refund\n- refund approved" in p or "- refund approved\n- customer asked for a refund" in p for p in prompts)
    assert await _memories(db_session, ids["busy"]) == [("episodic", "first contact"), ("long_term", "The refund was requested and approved.")]
    assert await _memories(db_session, ids["quiet"]) == [("short_term", "only one event")]
    assert await _memories(db_session, ids["llm_down"]) == [("short_term", "x"), ("short_term", "y")]  # an LLM error is a no-op, not a loss
    assert f"consolidate_agent_memory: agent '{broken_id}' failed: provider exploded" in caplog.text
    assert task_session == [True]


async def test_cleanup_forgets_only_old_short_term_memories(db_session, org_id, task_session, monkeypatch, caplog):
    first = await _agent(db_session, org_id, "first")
    second = await _agent(db_session, org_id, "second")
    db_session.add_all([
        _memory(first, "short_term", "stale", LONG_AGO), _memory(first, "short_term", "fresh"), _memory(first, "long_term", "old but kept", LONG_AGO),
        _memory(second, "short_term", "stale too", LONG_AGO), _memory(second, "episodic", "old episode", LONG_AGO),
    ])
    await db_session.commit()
    ids = {"first": first.id, "second": second.id}

    assert await agent_tasks._cleanup_old_memory_async(30) == 2

    assert await _memories(db_session, ids["first"]) == [("long_term", "old but kept"), ("short_term", "fresh")]
    assert await _memories(db_session, ids["second"]) == [("episodic", "old episode")]


async def test_cleanup_survives_one_agent_failing(db_session, org_id, task_session, monkeypatch, caplog):
    ok = await _agent(db_session, org_id, "ok")
    failing = await _agent(db_session, org_id, "failing")
    db_session.add(_memory(ok, "short_term", "stale", LONG_AGO))
    await db_session.commit()
    ids, failing_id = {"ok": ok.id}, failing.id
    from api.services import autonomous_agents as service

    real_forget = service.forget_old_memory

    async def forget(db, agent_id, days):
        if agent_id == failing_id:
            raise RuntimeError("lock timeout")
        return await real_forget(db, agent_id, days)

    monkeypatch.setattr(service, "forget_old_memory", forget)
    with caplog.at_level(logging.WARNING, logger="api.tasks.autonomous_agents"):
        assert await agent_tasks._cleanup_old_memory_async(30) == 1
    assert f"cleanup_old_memory: agent '{failing_id}' failed: lock timeout" in caplog.text
    assert await _memories(db_session, ids["ok"]) == []


async def test_guardrail_sweep_stops_only_agents_executing_for_too_long(db_session, org_id, task_session, monkeypatch):
    monkeypatch.setattr(settings, "AUTONOMOUS_MAX_DURATION", 600)
    stuck = await _agent(db_session, org_id, "stuck", status=AutonomousAgentStatus.executing.value, updated_at=LONG_AGO)
    running = await _agent(db_session, org_id, "running", status=AutonomousAgentStatus.executing.value)
    idle_old = await _agent(db_session, org_id, "idle-old", updated_at=LONG_AGO)

    assert await agent_tasks._check_agent_guardrails_async() == 1

    await db_session.rollback()
    for agent in (stuck, running, idle_old):
        await db_session.refresh(agent)
    assert stuck.status == AutonomousAgentStatus.error.value
    assert stuck.error == "Exceeded AUTONOMOUS_MAX_DURATION (600s) -- stopped by the real guardrail sweep."
    assert running.status == AutonomousAgentStatus.executing.value and running.error is None
    assert idle_old.status == AutonomousAgentStatus.idle.value


async def test_run_and_plan_jobs_commit_the_run_and_report_its_status(db_session, org_id, task_session, monkeypatch):
    agent = await _agent(db_session, org_id, "runner")
    plan = AgentPlan(agent_id=agent.id, goal="ship it")
    db_session.add(plan)
    await db_session.commit()
    agent_id, plan_id = agent.id, plan.id  # a "not_found" run rolls the session back, which expires every loaded object
    runs = []

    async def fake_run(db, agent_id):
        from api.services.autonomous_agents import AutonomousAgentNotFoundError

        found = await db.get(AutonomousAgent, agent_id)
        if found is None:
            raise AutonomousAgentNotFoundError(str(agent_id))
        runs.append(agent_id)
        found.status = AutonomousAgentStatus.completed.value
        return found

    monkeypatch.setattr("api.services.autonomous_agents.run_autonomous_agent", fake_run)

    assert await agent_tasks._run_autonomous_agent_async(str(agent_id)) == "completed"
    assert await agent_tasks._run_autonomous_agent_async(str(uuid.uuid4())) == "not_found"
    assert await agent_tasks._execute_agent_plan_async(str(plan_id)) == "completed"
    assert await agent_tasks._execute_agent_plan_async(str(uuid.uuid4())) == "not_found"
    assert runs == [agent_id, agent_id]  # the plan job drives the plan's own agent
    await db_session.rollback()
    await db_session.refresh(agent)
    assert agent.status == AutonomousAgentStatus.completed.value


def test_the_celery_entry_points_run_their_job_with_the_configured_values(monkeypatch):
    received = {}

    def recorder(name, value):
        async def _fake(*args):
            received[name] = args
            return value

        return _fake

    monkeypatch.setattr(agent_tasks, "_run_autonomous_agent_async", recorder("run", "completed"))
    monkeypatch.setattr(agent_tasks, "_execute_agent_plan_async", recorder("plan", "paused"))
    monkeypatch.setattr(agent_tasks, "_consolidate_agent_memory_async", recorder("consolidate", 2))
    monkeypatch.setattr(agent_tasks, "_cleanup_old_memory_async", recorder("cleanup", 3))
    monkeypatch.setattr(agent_tasks, "_check_agent_guardrails_async", recorder("guardrails", 4))
    monkeypatch.setattr(settings, "AUTONOMOUS_MEMORY_RETENTION_DAYS", 9)

    assert agent_tasks.run_autonomous_agent_task.run("a1") == "completed"
    assert agent_tasks.execute_agent_plan_task.run("p1") == "paused"
    assert (agent_tasks.consolidate_agent_memory.run(), agent_tasks.cleanup_old_memory.run(), agent_tasks.check_agent_guardrails.run()) == (2, 3, 4)
    assert received == {"run": ("a1",), "plan": ("p1",), "consolidate": (), "cleanup": (9,), "guardrails": ()}


def test_scheduling_a_run_dispatches_the_id_as_text_and_never_raises(monkeypatch, caplog):
    sent = []
    monkeypatch.setattr(agent_tasks.run_autonomous_agent_task, "delay", lambda agent_id: sent.append(agent_id))
    agent_id = uuid.uuid4()
    agent_tasks.schedule_autonomous_agent_run(agent_id)
    assert sent == [str(agent_id)]

    def broker_down(agent_id):
        raise ConnectionError("redis unreachable")

    monkeypatch.setattr(agent_tasks.run_autonomous_agent_task, "delay", broker_down)
    with caplog.at_level(logging.WARNING, logger="api.tasks.autonomous_agents"):
        agent_tasks.schedule_autonomous_agent_run(agent_id)
    assert f"could not schedule run for agent '{agent_id}': redis unreachable" in caplog.text
