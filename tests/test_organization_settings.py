"""
Partie 1.3.9 -- per-organization configuration. Fast SQLite suite, same
tier as tests/test_quotas.py.
"""

import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.organization_settings import OrganizationSettings
from api.models.user import User
from api.security.organization_settings import DEFAULT_SETTINGS


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def _add_member(db_session, org_id, user_id, role: OrganizationRole, invited_by=None):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


# --------------------------------------------------------------- defaults --

async def test_default_settings_are_created_with_the_organization(client, db_session, register_payload):
    """Validation criterion: default settings are created with the org."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    row = await db_session.scalar(select(OrganizationSettings).where(OrganizationSettings.organization_id == uuid.UUID(org["id"])))
    assert row is not None
    assert row.settings == {}  # no overrides yet -- every value resolves to DEFAULT_SETTINGS


async def test_the_default_org_created_at_registration_also_gets_settings(client, db_session, register_payload):
    """create_organization_with_owner is shared by POST /organizations
    AND registration's auto-default-org -- both paths must get a row."""
    _, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    membership = await db_session.scalar(select(OrganizationMember).where(OrganizationMember.user_id == owner.id))
    row = await db_session.scalar(select(OrganizationSettings).where(OrganizationSettings.organization_id == membership.organization_id))
    assert row is not None


async def test_get_settings_returns_every_documented_default(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.get(f"/organizations/{org['id']}/settings", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    for key, value in DEFAULT_SETTINGS.items():
        assert body[key] == value


async def test_get_settings_falls_back_to_defaults_when_no_row_exists(client, db_session, register_payload):
    """An organization that predates this migration (or whose row was
    deleted out of band) must not break -- get_org_settings degrades to
    pure defaults instead of raising."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    await db_session.execute(OrganizationSettings.__table__.delete().where(OrganizationSettings.organization_id == org_id))
    await db_session.commit()

    response = await client.get(f"/organizations/{org['id']}/settings", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["chunk_size"] == DEFAULT_SETTINGS["chunk_size"]


# ---------------------------------------------------------------- reading --

async def test_admin_can_view_settings(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin = await _register(client, db_session, "settingsadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/settings", headers=_auth_header(admin_token))
    assert response.status_code == 200


async def test_manager_cannot_view_settings(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager = await _register(client, db_session, "settingsmanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/settings", headers=_auth_header(manager_token))
    assert response.status_code == 403


async def test_a_member_of_another_organization_cannot_view_this_organizations_settings(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    outsider_token, outsider = await _register(client, db_session, "settingsoutsider@example.com")

    response = await client.get(f"/organizations/{org['id']}/settings", headers=_auth_header(outsider_token))
    assert response.status_code == 404  # anti-enumeration, same as require_org_member elsewhere


# --------------------------------------------------------------- writing --

async def test_only_owner_can_update_settings(client, db_session, register_payload):
    """Validation criterion: only Owner can modify settings."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin = await _register(client, db_session, "settingspatchadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    blocked = await client.patch(
        f"/organizations/{org['id']}/settings", json={"chunk_size": 1024}, headers=_auth_header(admin_token),
    )
    assert blocked.status_code == 403

    allowed = await client.patch(
        f"/organizations/{org['id']}/settings", json={"chunk_size": 1024}, headers=_auth_header(owner_token),
    )
    assert allowed.status_code == 200
    assert allowed.json()["chunk_size"] == 1024


async def test_updating_one_field_leaves_others_at_their_default(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/settings", json={"temperature": 0.2}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["temperature"] == 0.2
    assert body["top_k"] == DEFAULT_SETTINGS["top_k"]  # untouched
    assert body["llm_provider"] == DEFAULT_SETTINGS["llm_provider"]  # untouched


async def test_updated_settings_persist_across_requests(client, db_session, register_payload):
    """Validation criterion: updated settings are applied."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    await client.patch(
        f"/organizations/{org['id']}/settings",
        json={"llm_provider": "openai", "llm_model": "gpt-4o", "system_prompt": "Be terse."},
        headers=_auth_header(owner_token),
    )

    second_read = await client.get(f"/organizations/{org['id']}/settings", headers=_auth_header(owner_token))
    body = second_read.json()
    assert body["llm_provider"] == "openai"
    assert body["llm_model"] == "gpt-4o"
    assert body["system_prompt"] == "Be terse."


async def test_multiple_partial_updates_accumulate(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    await client.patch(f"/organizations/{org['id']}/settings", json={"chunk_size": 1024}, headers=_auth_header(owner_token))
    second = await client.patch(f"/organizations/{org['id']}/settings", json={"top_k": 10}, headers=_auth_header(owner_token))

    body = second.json()
    assert body["chunk_size"] == 1024  # from the first PATCH, still in effect
    assert body["top_k"] == 10  # from the second PATCH


async def test_patching_a_predates_migration_organization_creates_its_settings_row(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    await db_session.execute(OrganizationSettings.__table__.delete().where(OrganizationSettings.organization_id == org_id))
    await db_session.commit()

    response = await client.patch(f"/organizations/{org['id']}/settings", json={"chunk_size": 999}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["chunk_size"] == 999

    row = await db_session.scalar(select(OrganizationSettings).where(OrganizationSettings.organization_id == org_id))
    assert row is not None


# ------------------------------------------------------------- validation --

async def test_chunk_overlap_must_be_smaller_than_chunk_size(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/settings", json={"chunk_overlap": 600}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400  # default chunk_size is 512, 600 >= 512

    together = await client.patch(
        f"/organizations/{org['id']}/settings", json={"chunk_size": 1024, "chunk_overlap": 600}, headers=_auth_header(owner_token),
    )
    assert together.status_code == 200


async def test_invalid_llm_provider_is_rejected(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/settings", json={"llm_provider": "not-a-real-provider"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 422


async def test_invalid_retrieval_strategy_is_rejected(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/settings", json={"retrieval_strategy": "magic"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 422


async def test_negative_chunk_size_is_rejected(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/settings", json={"chunk_size": -1}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 422


async def test_score_threshold_defaults_and_can_be_updated(client, db_session, register_payload):
    """Partie 3.3.7."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    default_response = await client.get(f"/organizations/{org['id']}/settings", headers=_auth_header(owner_token))
    assert default_response.json()["score_threshold"] == DEFAULT_SETTINGS["score_threshold"]

    updated = await client.patch(
        f"/organizations/{org['id']}/settings", json={"score_threshold": 0.8}, headers=_auth_header(owner_token),
    )
    assert updated.json()["score_threshold"] == 0.8


async def test_score_threshold_outside_0_1_is_rejected(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    negative = await client.patch(
        f"/organizations/{org['id']}/settings", json={"score_threshold": -0.1}, headers=_auth_header(owner_token),
    )
    assert negative.status_code == 422

    too_high = await client.patch(
        f"/organizations/{org['id']}/settings", json={"score_threshold": 1.1}, headers=_auth_header(owner_token),
    )
    assert too_high.status_code == 422


async def test_rrf_k_defaults_and_can_be_updated(client, db_session, register_payload):
    """Partie 3.4.7."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    default_response = await client.get(f"/organizations/{org['id']}/settings", headers=_auth_header(owner_token))
    assert default_response.json()["rrf_k"] == DEFAULT_SETTINGS["rrf_k"]

    updated = await client.patch(
        f"/organizations/{org['id']}/settings", json={"rrf_k": 120}, headers=_auth_header(owner_token),
    )
    assert updated.json()["rrf_k"] == 120


async def test_rrf_k_outside_1_1000_is_rejected(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    zero = await client.patch(f"/organizations/{org['id']}/settings", json={"rrf_k": 0}, headers=_auth_header(owner_token))
    assert zero.status_code == 422

    too_high = await client.patch(f"/organizations/{org['id']}/settings", json={"rrf_k": 1001}, headers=_auth_header(owner_token))
    assert too_high.status_code == 422


async def test_top_p_defaults_and_can_be_updated(client, db_session, register_payload):
    """Partie 4.3.3."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    default_response = await client.get(f"/organizations/{org['id']}/settings", headers=_auth_header(owner_token))
    assert default_response.json()["top_p"] == DEFAULT_SETTINGS["top_p"]

    updated = await client.patch(f"/organizations/{org['id']}/settings", json={"top_p": 0.5}, headers=_auth_header(owner_token))
    assert updated.json()["top_p"] == 0.5


async def test_top_p_outside_0_1_is_rejected(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    negative = await client.patch(f"/organizations/{org['id']}/settings", json={"top_p": -0.1}, headers=_auth_header(owner_token))
    assert negative.status_code == 422

    too_high = await client.patch(f"/organizations/{org['id']}/settings", json={"top_p": 1.1}, headers=_auth_header(owner_token))
    assert too_high.status_code == 422


async def test_max_tokens_above_the_real_ceiling_is_rejected(client, db_session, register_payload):
    """Partie 4.3.5's own real gap fix -- max_tokens previously had no
    upper bound at all."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    too_high = await client.patch(f"/organizations/{org['id']}/settings", json={"max_tokens": 32769}, headers=_auth_header(owner_token))
    assert too_high.status_code == 422

    at_ceiling = await client.patch(f"/organizations/{org['id']}/settings", json={"max_tokens": 32768}, headers=_auth_header(owner_token))
    assert at_ceiling.status_code == 200


async def test_out_of_range_temperature_is_rejected(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/settings", json={"temperature": 3.5}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 422


async def test_unknown_timezone_is_rejected(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/settings", json={"timezone": "Mars/OlympusMons"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 422


async def test_valid_timezone_is_accepted(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/settings", json={"timezone": "Europe/Paris"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["timezone"] == "Europe/Paris"


async def test_invalid_language_code_is_rejected(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/settings", json={"language": "english"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 422
