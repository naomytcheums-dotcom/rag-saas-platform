"""Partie 5.2.10 -- custom tools (webhooks). Real httpx.MockTransport
at the webhook boundary, same precedent as tests/test_web_search.py."""

import uuid

import httpx
import pytest
from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.custom_tools import (
    CustomToolError, create_custom_tool, delete_custom_tool, get_custom_tool, get_custom_tools, update_custom_tool,
)
from api.services.custom_tools import (
    execute_custom_tool, format_webhook_response, get_available_custom_tools, validate_custom_tool_input,
)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Real retries use real exponential backoff -- same real,
    test-only speed-up precedent as tests/test_agent_orchestrator.py."""
    async def _instant_sleep(_seconds):
        return None

    monkeypatch.setattr("asyncio.sleep", _instant_sleep)


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr("api.services.url_fetching._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


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


_VALID_DATA = {"name": "Weather", "description": "Get the weather", "webhook_url": "https://example.com/weather", "schema": {}}


# --------------------------------------- create/update/get/list/delete --


async def test_create_custom_tool_persists_real_values(db_session):
    """Validation criterion: la création d'outil fonctionne."""
    tool = await create_custom_tool(db_session, uuid.uuid4(), _VALID_DATA, None)
    await db_session.commit()
    assert tool.name == "Weather"
    assert tool.method == "POST"
    assert tool.retry_count == 1


async def test_create_custom_tool_rejects_an_unknown_method(db_session):
    with pytest.raises(CustomToolError, match="Unknown method"):
        await create_custom_tool(db_session, uuid.uuid4(), {**_VALID_DATA, "method": "TRACE"}, None)


async def test_create_custom_tool_rejects_a_non_positive_timeout(db_session):
    with pytest.raises(CustomToolError):
        await create_custom_tool(db_session, uuid.uuid4(), {**_VALID_DATA, "timeout": 0}, None)


async def test_update_custom_tool_changes_only_given_fields(db_session):
    tool = await create_custom_tool(db_session, uuid.uuid4(), _VALID_DATA, None)
    await db_session.commit()
    updated = await update_custom_tool(db_session, tool.id, {"description": "Updated"})
    await db_session.commit()
    assert updated.description == "Updated"
    assert updated.name == "Weather"


async def test_get_custom_tools_lists_only_this_organizations_tools(db_session):
    """Validation criterion: isolation par organisation."""
    org_id = uuid.uuid4()
    await create_custom_tool(db_session, org_id, _VALID_DATA, None)
    await create_custom_tool(db_session, uuid.uuid4(), _VALID_DATA, None)
    await db_session.commit()

    tools = await get_custom_tools(db_session, org_id)
    assert len(tools) == 1


async def test_delete_custom_tool_is_a_real_soft_delete(db_session):
    tool = await create_custom_tool(db_session, uuid.uuid4(), _VALID_DATA, None)
    await db_session.commit()

    assert await delete_custom_tool(db_session, tool.id) is True
    await db_session.commit()
    assert await get_custom_tool(db_session, tool.id) is None


# --------------------------------------- validate_custom_tool_input / format_webhook_response --


async def test_validate_custom_tool_input_accepts_real_matching_params(db_session):
    """Validation criterion: la validation fonctionne."""
    tool = await create_custom_tool(
        db_session, uuid.uuid4(), {**_VALID_DATA, "schema": {"type": "object", "required": ["city"]}}, None,
    )
    await db_session.commit()
    validate_custom_tool_input(tool, {"city": "Paris"})


async def test_validate_custom_tool_input_rejects_missing_required_params(db_session):
    tool = await create_custom_tool(
        db_session, uuid.uuid4(), {**_VALID_DATA, "schema": {"type": "object", "required": ["city"]}}, None,
    )
    await db_session.commit()
    with pytest.raises(CustomToolError, match="Invalid input"):
        validate_custom_tool_input(tool, {})


def test_format_webhook_response_parses_real_json():
    response = httpx.Response(200, json={"temp": 20}, request=httpx.Request("POST", "https://example.com"))
    assert format_webhook_response(response) == {"status_code": 200, "headers": dict(response.headers), "body": {"temp": 20}}


# --------------------------------------- execute_custom_tool --


async def test_execute_custom_tool_calls_the_real_webhook(monkeypatch, db_session):
    """Validation criterion: l'exécution fonctionne."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.com/weather"
        return httpx.Response(200, json={"temp": 20})

    _patch_client(monkeypatch, handler)
    tool = await create_custom_tool(db_session, uuid.uuid4(), _VALID_DATA, None)
    await db_session.commit()

    result = await execute_custom_tool(db_session, tool.id, {"city": "Paris"})
    assert result["body"] == {"temp": 20}


async def test_execute_custom_tool_sends_get_params_as_query_string(monkeypatch, db_session):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["city"] == "Paris"
        return httpx.Response(200, json={})

    _patch_client(monkeypatch, handler)
    tool = await create_custom_tool(db_session, uuid.uuid4(), {**_VALID_DATA, "method": "GET"}, None)
    await db_session.commit()

    await execute_custom_tool(db_session, tool.id, {"city": "Paris"})


async def test_execute_custom_tool_rejects_invalid_params(db_session):
    tool = await create_custom_tool(
        db_session, uuid.uuid4(), {**_VALID_DATA, "schema": {"type": "object", "required": ["city"]}}, None,
    )
    await db_session.commit()
    with pytest.raises(CustomToolError):
        await execute_custom_tool(db_session, tool.id, {})


async def test_execute_custom_tool_retries_on_a_real_transient_failure(monkeypatch, db_session):
    """Validation criterion: robustesse -- que se passe-t-il si le webhook échoue (retry)."""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(200, json={"ok": True})

    _patch_client(monkeypatch, handler)
    tool = await create_custom_tool(db_session, uuid.uuid4(), {**_VALID_DATA, "retry_count": 3}, None)
    await db_session.commit()

    result = await execute_custom_tool(db_session, tool.id, {})
    assert result["body"] == {"ok": True}
    assert attempts["count"] == 2


async def test_execute_custom_tool_raises_after_exhausting_real_retries(monkeypatch, db_session):
    """Validation criterion: robustesse -- échec persistant après épuisement des tentatives."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _patch_client(monkeypatch, handler)
    tool = await create_custom_tool(db_session, uuid.uuid4(), {**_VALID_DATA, "retry_count": 2}, None)
    await db_session.commit()

    with pytest.raises(CustomToolError, match="webhook failed"):
        await execute_custom_tool(db_session, tool.id, {})


async def test_execute_custom_tool_does_not_retry_on_a_real_4xx_response(monkeypatch, db_session):
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(400, text="bad request")

    _patch_client(monkeypatch, handler)
    tool = await create_custom_tool(db_session, uuid.uuid4(), {**_VALID_DATA, "retry_count": 3}, None)
    await db_session.commit()

    with pytest.raises(CustomToolError):
        await execute_custom_tool(db_session, tool.id, {})
    assert attempts["count"] == 1


async def test_execute_custom_tool_raises_for_an_unknown_tool(db_session):
    with pytest.raises(CustomToolError, match="Unknown custom tool"):
        await execute_custom_tool(db_session, uuid.uuid4(), {})


# --------------------------------------- orchestrator integration --


async def test_get_available_custom_tools_returns_real_usable_toolspecs(monkeypatch, db_session):
    """Validation criterion: l'agent peut appeler les outils personnalisés."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"temp": 20})

    _patch_client(monkeypatch, handler)
    org_id = uuid.uuid4()
    await create_custom_tool(db_session, org_id, _VALID_DATA, None)
    await db_session.commit()

    specs = await get_available_custom_tools(db_session, org_id)
    assert len(specs) == 1
    assert specs[0].name == "Weather"
    result = await specs[0].handler(city="Paris")
    assert "20" in result


# --------------------------------------- endpoints --


async def test_manager_can_create_and_list_custom_tools(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    create_response = await client.post(f"/organizations/{org['id']}/custom-tools", json=_VALID_DATA, headers=_auth_header(owner_token))
    assert create_response.status_code == 201
    assert create_response.json()["schema"] == {}

    list_response = await client.get(f"/organizations/{org['id']}/custom-tools", headers=_auth_header(owner_token))
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


async def test_member_cannot_create_a_custom_tool(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.post(f"/organizations/{org['id']}/custom-tools", json=_VALID_DATA, headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_member_can_read_and_execute_a_custom_tool(monkeypatch, client, db_session, register_payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"temp": 20})

    _patch_client(monkeypatch, handler)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/custom-tools", json=_VALID_DATA, headers=_auth_header(owner_token))
    tool_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    get_response = await client.get(f"/custom-tools/{tool_id}", headers=_auth_header(member_token))
    assert get_response.status_code == 200

    execute_response = await client.post(f"/custom-tools/{tool_id}/execute", json={"params": {}}, headers=_auth_header(member_token))
    assert execute_response.status_code == 200
    assert execute_response.json()["body"] == {"temp": 20}


async def test_manager_can_update_and_delete_a_custom_tool(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/custom-tools", json=_VALID_DATA, headers=_auth_header(owner_token))
    tool_id = created.json()["id"]

    patch_response = await client.patch(f"/custom-tools/{tool_id}", json={"description": "Updated"}, headers=_auth_header(owner_token))
    assert patch_response.status_code == 200
    assert patch_response.json()["description"] == "Updated"

    delete_response = await client.delete(f"/custom-tools/{tool_id}", headers=_auth_header(owner_token))
    assert delete_response.status_code == 204

    after_delete = await client.get(f"/custom-tools/{tool_id}", headers=_auth_header(owner_token))
    assert after_delete.status_code == 404


async def test_cannot_access_a_custom_tool_from_another_organization(client, db_session, register_payload):
    """Validation criterion: sécurité -- isolation par organisation."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/custom-tools", json=_VALID_DATA, headers=_auth_header(owner_token))
    tool_id = created.json()["id"]

    other_token, other_owner = await _register(client, db_session, "other@example.com")
    response = await client.get(f"/custom-tools/{tool_id}", headers=_auth_header(other_token))
    assert response.status_code == 404
