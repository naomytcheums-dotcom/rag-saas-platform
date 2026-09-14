"""Partie 24 -- real fine-tuned model deploy/undeploy/delete/list and
access control."""

import uuid

from sqlalchemy import select

from api.models.fine_tuning import FineTunedModel, FineTunedModelStatus, FineTuningDataset, FineTuningJob
from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org(client, db_session, register_payload, name):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    return owner_token, org_id


async def _make_model(db_session, org_id, **kwargs) -> FineTunedModel:
    dataset = FineTuningDataset(organization_id=uuid.UUID(org_id), name="D", dataset_type="llm", format="jsonl", file_key="k", size=1, status="ready")
    db_session.add(dataset)
    await db_session.flush()
    job = FineTuningJob(organization_id=uuid.UUID(org_id), dataset_id=dataset.id, name="J", base_model="gpt-4o-mini-2024-07-18", provider="openai")
    db_session.add(job)
    await db_session.flush()
    model = FineTunedModel(
        organization_id=uuid.UUID(org_id), job_id=job.id, name="M", provider="openai",
        provider_model_id="ft:gpt-4o-mini-2024-07-18:acme::abc123", base_model="gpt-4o-mini-2024-07-18", **kwargs,
    )
    db_session.add(model)
    await db_session.flush()
    return model


async def test_deploy_and_undeploy_model(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Deploy Org")
    model = await _make_model(db_session, org_id)
    await db_session.commit()

    response = await client.post(f"/fine-tuning/models/{model.id}/deploy", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["deployed"] is True

    response = await client.post(f"/fine-tuning/models/{model.id}/undeploy", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["deployed"] is False


async def test_cannot_deploy_a_deprecated_model(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Deprecated Org")
    model = await _make_model(db_session, org_id, status=FineTunedModelStatus.deprecated.value)
    await db_session.commit()

    response = await client.post(f"/fine-tuning/models/{model.id}/deploy", headers=_auth_header(owner_token))
    assert response.status_code == 400


async def test_list_models_scoped_to_own_organization(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "List Models Org")
    await _make_model(db_session, org_id)
    await db_session.commit()

    response = await client.get(f"/fine-tuning/models?org_id={org_id}", headers=_auth_header(owner_token))
    assert response.json()["total"] == 1


async def test_delete_model_requires_admin(client, db_session, register_payload):
    from api.models.organization import OrganizationMember, OrganizationRole

    owner_token, org_id = await _make_org(client, db_session, register_payload, "Delete Model Org")
    model = await _make_model(db_session, org_id)

    member_token, member = await _register(client, db_session, "ft_model_member@example.com")
    owner = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org_id), user_id=member.id, role=OrganizationRole.member, invited_by=owner.id))
    await db_session.commit()

    response = await client.delete(f"/fine-tuning/models/{model.id}", headers=_auth_header(member_token))
    assert response.status_code == 403

    response = await client.delete(f"/fine-tuning/models/{model.id}", headers=_auth_header(owner_token))
    assert response.status_code == 204
    assert await db_session.get(FineTunedModel, model.id) is None
