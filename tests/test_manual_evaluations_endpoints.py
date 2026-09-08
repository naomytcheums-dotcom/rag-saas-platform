"""Partie 7.3.2 -- manual (human) evaluation endpoints. Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org_dataset_and_question(client, db_session, register_payload, name):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    dataset = (await client.post(f"/organizations/{org_id}/datasets", json={"name": "D"}, headers=_auth_header(owner_token))).json()
    question = (await client.post(f"/datasets/{dataset['id']}/questions", json={"question": "Q?"}, headers=_auth_header(owner_token))).json()
    return owner_token, org_id, dataset, question


async def _add_member(client, db_session, org_id, email):
    """Registers a second real user and inserts a real Member (not
    Owner/Admin) row directly -- same real, direct-DB shortcut
    tests/test_invitations.py's own suite already uses, sidestepping
    the real email-invitation flow entirely."""
    member_token, member = await _register(client, db_session, email)
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org_id), user_id=member.id, role=OrganizationRole.member))
    await db_session.commit()
    return member_token, member


async def test_create_manual_evaluation_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la création d'évaluation fonctionne."""
    owner_token, _org_id, _dataset, question = await _make_org_dataset_and_question(client, db_session, register_payload, "Manual Eval Endpoint Org")
    response = await client.post(
        f"/questions/{question['id']}/evaluate", json={"score": 4, "feedback": "Good.", "criteria": {"accuracy": 5}},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    assert response.json()["score"] == 4


async def test_update_manual_evaluation_endpoint_works_for_the_owner(client, db_session, register_payload):
    """Validation criterion: la modification fonctionne."""
    owner_token, _org_id, _dataset, question = await _make_org_dataset_and_question(client, db_session, register_payload, "Manual Eval Update Endpoint Org")
    evaluation = (await client.post(f"/questions/{question['id']}/evaluate", json={"score": 2}, headers=_auth_header(owner_token))).json()

    response = await client.patch(f"/evaluations/{evaluation['id']}", json={"score": 5}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["score"] == 5


async def test_get_manual_evaluation_stats_endpoint_works(client, db_session, register_payload):
    """Validation criterion: les statistiques sont correctes."""
    owner_token, _org_id, dataset, question = await _make_org_dataset_and_question(client, db_session, register_payload, "Manual Eval Stats Endpoint Org")
    await client.post(f"/questions/{question['id']}/evaluate", json={"score": 4}, headers=_auth_header(owner_token))

    response = await client.get(f"/datasets/{dataset['id']}/evaluations/stats", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["average_score"] == 4.0


async def test_create_manual_evaluation_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, _org_id, _dataset, question = await _make_org_dataset_and_question(client, db_session, register_payload, "Manual Eval Perms Org")
    other_token, _other = await _register(client, db_session, "non-member-manual-eval@example.com")

    response = await client.post(f"/questions/{question['id']}/evaluate", json={"score": 3}, headers=_auth_header(other_token))
    assert response.status_code == 404


async def test_get_manual_evaluation_stats_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées -- stats
    are Admin+, a real Member alone must not reach them."""
    owner_token, org_id, dataset, _question = await _make_org_dataset_and_question(client, db_session, register_payload, "Manual Eval Stats Perms Org")
    member_token, _member = await _add_member(client, db_session, org_id, "member-manual-eval-stats@example.com")

    response = await client.get(f"/datasets/{dataset['id']}/evaluations/stats", headers=_auth_header(member_token))
    assert response.status_code == 403
