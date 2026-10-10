"""TEN-012: a read-only viewer can read a workflow but not run it (running costs credits and can have side effects)."""

import datetime as dt
from unittest.mock import Mock

from api.config import settings
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User
from api.models.workflow import Workflow
from api.security.jwt import create_access_token


async def _member(db_session, org_id, email, role):
    user = User(
        email=email, hashed_password="unused", is_email_verified=True,
        terms_version=settings.TERMS_VERSION, consent_given_at=dt.datetime.now(dt.timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user.id, role=role))
    await db_session.commit()
    token, _ = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


async def test_only_member_and_above_may_run_a_workflow(client, db_session, monkeypatch):
    schedule = Mock()
    monkeypatch.setattr("api.routers.workflows.schedule_workflow_run", schedule)
    org = Organization(name="Wf Org", slug="wf-org-ten012")
    db_session.add(org)
    await db_session.flush()
    workflow = Workflow(organization_id=org.id, name="w", nodes=[], edges=[])
    db_session.add(workflow)
    await db_session.commit()
    viewer = await _member(db_session, org.id, "ten012-viewer@example.com", OrganizationRole.viewer)
    member = await _member(db_session, org.id, "ten012-member@example.com", OrganizationRole.member)

    assert (await client.get(f"/workflows/{workflow.id}", headers=viewer)).status_code == 200  # reading stays allowed

    refused = await client.post(f"/workflows/{workflow.id}/run", json={}, headers=viewer)
    assert refused.status_code == 403
    schedule.assert_not_called()

    allowed = await client.post(f"/workflows/{workflow.id}/run", json={}, headers=member)
    assert allowed.status_code == 200, allowed.text
    schedule.assert_called_once()
