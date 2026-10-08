"""P2C-3: persisted foreign workflow, run, trigger and human-block IDs."""

from unittest.mock import Mock

from sqlalchemy import func, select

from api.models.workflow import Workflow
from api.models.workflow_human_input import WorkflowHumanInput
from api.models.workflow_run import WorkflowRun, WorkflowTrigger
from test_document_idor import denied, make_tenants, snapshot


async def test_workflow_idor(client, db_session, monkeypatch):
    (owner, org_a, _), (attacker, _, _) = await make_tenants(
        client, db_session, monkeypatch, "workflow"
    )
    workflow = Workflow(organization_id=org_a, name="private-workflow", nodes=[], edges=[])
    db_session.add(workflow)
    await db_session.flush()
    trigger = WorkflowTrigger(
        workflow_id=workflow.id, type="webhook", webhook_token="p2c-local-webhook-secret"
    )
    run = WorkflowRun(workflow_id=workflow.id, status="waiting_human", input={"private": "input"})
    db_session.add_all([trigger, run])
    await db_session.flush()
    block = WorkflowHumanInput(
        workflow_run_id=run.id, node_id="human", message="private-approval"
    )
    db_session.add(block)
    await db_session.commit()
    baseline = await snapshot(db_session, workflow, trigger, run, block)
    workflow_id, run_id, trigger_id, block_id = workflow.id, run.id, trigger.id, block.id
    schedule, resume = Mock(), Mock()
    monkeypatch.setattr("api.routers.workflows.schedule_workflow_run", schedule)
    monkeypatch.setattr("api.routers.workflows.schedule_workflow_resume", resume)
    control = await client.get(f"/workflows/{workflow_id}", headers=owner)
    assert control.status_code == 200, control.text
    violations = []
    for suffix in ("", "/export", "/triggers", "/runs", "/versions"):
        await denied(client, "GET", f"/workflows/{workflow_id}{suffix}", attacker, violations)
    await denied(
        client, "PATCH", f"/workflows/{workflow_id}", attacker, violations,
        json={"name": "attacker-rename"},
    )
    await denied(
        client, "POST", f"/workflows/{workflow_id}/run", attacker, violations,
        json={"input": {"attacker": True}},
    )
    for suffix in ("", "/trace", "/stream", "/human-blocks", f"/human-blocks/{block_id}"):
        await denied(client, "GET", f"/workflows/runs/{run_id}{suffix}", attacker, violations)
    await denied(
        client, "POST", f"/workflows/runs/{run_id}/human-blocks/{block_id}/submit",
        attacker, violations, json={"value": {"text": "attacker"}},
    )
    await denied(
        client, "DELETE", f"/workflows/{workflow_id}/triggers/{trigger_id}",
        attacker, violations,
    )
    await denied(
        client, "POST", f"/webhooks/{trigger_id}",
        {**attacker, "X-Webhook-Token": "wrong-local-secret"}, violations,
        expected=(401,), json={"input": {}},
    )
    await denied(client, "DELETE", f"/workflows/{workflow_id}", attacker, violations)
    assert await snapshot(db_session, workflow, trigger, run, block) == baseline
    assert await db_session.scalar(select(func.count()).select_from(WorkflowRun)) == 1
    schedule.assert_not_called()
    resume.assert_not_called()
    assert not violations, "\n".join(violations)
