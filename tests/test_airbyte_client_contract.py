"""Contract tests of api/services/airbyte_client.py against a LOCAL FAKE Airbyte API (tests/vendor_fakes.py), not the real service.

They prove our requests (paths, bodies, auth header) and our reading of the answers match the shapes the module documents; they say nothing about Airbyte itself."""

import sys
import uuid
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vendor_fakes import FakeVendor, Resp  # noqa: E402

from api.config import settings  # noqa: E402
from api.models.integrations import AirbyteConnection  # noqa: E402
from api.models.organization import Organization  # noqa: E402
from api.services import airbyte_client as airbyte  # noqa: E402


@pytest.fixture
def vendor(monkeypatch):
    monkeypatch.setattr(airbyte, "_cached_token", None)
    monkeypatch.setattr(airbyte, "_cached_token_expires_at", 0.0)
    with FakeVendor() as fake:
        monkeypatch.setattr(settings, "AIRBYTE_API_URL", fake.url)
        monkeypatch.setattr(settings, "AIRBYTE_WORKSPACE_ID", "ws-1")
        monkeypatch.setattr(settings, "AIRBYTE_API_KEY", None)
        monkeypatch.setattr(settings, "AIRBYTE_CLIENT_ID", None)
        monkeypatch.setattr(settings, "AIRBYTE_CLIENT_SECRET", None)
        yield fake


@pytest.fixture
def oss(vendor, monkeypatch):
    monkeypatch.setattr(settings, "AIRBYTE_API_KEY", "oss-static-key")
    return vendor


@pytest.fixture
def cloud(vendor, monkeypatch):
    monkeypatch.setattr(settings, "AIRBYTE_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "AIRBYTE_CLIENT_SECRET", "csecret")
    vendor.on("POST", "/applications/token", Resp(200, {"access_token": "cloud-token", "expires_in": 3600}))
    return vendor


async def test_without_any_credentials_every_call_is_a_clear_not_configured_error(vendor):
    for call in (airbyte.list_source_definitions, lambda: airbyte.trigger_sync("c"), lambda: airbyte.get_sync_status("j"), lambda: airbyte.get_source_catalog("s")):
        with pytest.raises(airbyte.AirbyteNotConfiguredError, match="AIRBYTE_API_URL"):
            await call()
    assert vendor.requests == []  # nothing was sent anywhere


async def test_a_url_without_credentials_is_still_not_configured(vendor, monkeypatch):
    monkeypatch.setattr(settings, "AIRBYTE_API_URL", "")
    monkeypatch.setattr(settings, "AIRBYTE_API_KEY", "key")
    with pytest.raises(airbyte.AirbyteNotConfiguredError):
        await airbyte.trigger_sync("c")


async def test_the_oss_static_key_is_sent_as_a_bearer_token_and_definitions_are_remapped(oss):
    oss.on("GET", "/workspaces/ws-1/definitions/sources", Resp(200, {"data": [{"id": "def-1", "name": "Postgres", "dockerRepository": "airbyte/source-postgres"}, {"id": "def-2", "name": "Notion"}]}))

    definitions = await airbyte.list_source_definitions()

    assert definitions == [
        {"sourceDefinitionId": "def-1", "name": "Postgres", "dockerRepository": "airbyte/source-postgres"},
        {"sourceDefinitionId": "def-2", "name": "Notion", "dockerRepository": None},
    ]
    assert oss.requests[0].headers["authorization"] == "Bearer oss-static-key"


async def test_cloud_credentials_are_exchanged_once_and_the_token_is_reused(cloud):
    cloud.on("POST", "/jobs", Resp(200, {"jobId": 7, "status": "pending"}))

    first = await airbyte.trigger_sync("conn-1")
    await airbyte.trigger_sync("conn-1")

    assert first == {"jobId": 7, "status": "pending"}
    token_calls = cloud.calls("POST", "/applications/token")
    assert len(token_calls) == 1  # cached until close to expiry
    assert token_calls[0].json() == {"client_id": "cid", "client_secret": "csecret", "grant_type": "client_credentials"}
    assert all(r.headers["authorization"] == "Bearer cloud-token" for r in cloud.calls("POST", "/jobs"))


async def test_a_failed_token_exchange_is_an_auth_error_that_never_leaks_the_secret(cloud):
    cloud._routes.clear()
    cloud.on("POST", "/applications/token", Resp(401, {"message": "invalid client"}))

    with pytest.raises(airbyte.AirbyteAuthError, match="HTTP 401") as raised:
        await airbyte.trigger_sync("conn-1")

    assert "csecret" not in str(raised.value)


async def test_create_source_sends_the_cloud_shape(oss):
    oss.on("POST", "/sources", Resp(200, {"sourceId": "src-9"}))

    result = await airbyte.create_source(name="crm", source_definition_id="def-1", connection_configuration={"host": "h"})

    assert result == {"sourceId": "src-9"}
    assert oss.calls("POST", "/sources")[0].json() == {"workspaceId": "ws-1", "name": "crm", "definitionId": "def-1", "configuration": {"host": "h"}}


async def test_the_catalog_is_read_fresh_not_from_airbytes_cache(oss):
    oss.on("GET", "/streams", Resp(200, {"streams": [{"streamName": "users"}]}))

    assert await airbyte.get_source_catalog("src-9") == {"streams": [{"streamName": "users"}]}

    assert oss.requests[0].query == {"sourceId": ["src-9"], "ignoreCache": ["true"]}


async def test_a_connection_carries_per_stream_settings_only_when_the_caller_gave_some(oss):
    oss.on("POST", "/connections", Resp(200, {"connectionId": "c-1"}))

    await airbyte.create_connection(source_id="s", destination_id="d", sync_catalog={})
    await airbyte.create_connection(source_id="s", destination_id="d", sync_catalog={"streams": [{"name": "users"}]})

    bodies = [r.json() for r in oss.calls("POST", "/connections")]
    assert bodies[0] == {"sourceId": "s", "destinationId": "d"}  # empty means Airbyte's own defaults, not "sync nothing"
    assert bodies[1] == {"sourceId": "s", "destinationId": "d", "configurations": {"streams": [{"name": "users"}]}}


async def test_triggering_a_sync_creates_a_sync_job_and_the_job_can_be_read_back(oss):
    oss.on("POST", "/jobs", Resp(200, {"jobId": 42}))
    oss.on("GET", "/jobs/42", Resp(200, {"jobId": 42, "status": "succeeded"}))

    assert (await airbyte.trigger_sync("conn-1"))["jobId"] == 42
    assert await airbyte.get_sync_status("42") == {"jobId": 42, "status": "succeeded"}

    assert oss.calls("POST", "/jobs")[0].json() == {"connectionId": "conn-1", "jobType": "sync"}


async def test_vendor_errors_surface_as_http_errors_for_the_caller_to_report(oss):
    oss.on("POST", "/jobs", Resp(500, {"message": "boom"}))
    oss.on("GET", "/jobs/*", Resp(404, {"message": "no such job"}))

    with pytest.raises(httpx.HTTPStatusError):
        await airbyte.trigger_sync("conn-1")
    with pytest.raises(httpx.HTTPStatusError):
        await airbyte.get_sync_status("nope")


async def test_recorded_connections_are_listed_per_organization(db_session):
    org_a, org_b = Organization(name="A", slug=f"a-{uuid.uuid4().hex[:8]}"), Organization(name="B", slug=f"b-{uuid.uuid4().hex[:8]}")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    recorded = await airbyte.record_connection(db_session, org_a.id, name="crm", airbyte_source_id="s", airbyte_connection_id="c", source_type="postgres", user_id=None)
    await airbyte.record_connection(db_session, org_b.id, name="other", airbyte_source_id="s2", airbyte_connection_id="c2", source_type="notion", user_id=None)

    listed = await airbyte.list_connections(db_session, org_a.id)
    assert [c.id for c in listed] == [recorded.id] and isinstance(listed[0], AirbyteConnection)  # another organization's connection is never listed
