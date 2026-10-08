"""Hardening Mission, §38 -- request correlation that actually correlates.

`RequestIdFilter` was attached to the ROOT logger, but a logger's filters only
apply to records created by that very logger: a record from `api.services.x`
never passed through it, so `request_id` was `None` on virtually every
application log line. Identifiers are now attached by a `LogRecord` factory
(runs for every record) and the tenant/user/run context is bound per request.
Real logging objects and a real (mini) ASGI app with the real middleware."""

import json
import logging
import uuid

import httpx
import pytest
from fastapi import FastAPI

from api.security import logging_correlation as lc


@pytest.fixture(autouse=True)
def _factory_and_capture():
    lc.configure_structured_logging("text")
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = _Capture(level=logging.DEBUG)
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    yield records
    root.removeHandler(handler)
    root.setLevel(previous_level)


def test_a_child_logger_record_carries_the_request_id_which_the_old_root_filter_never_delivered(_factory_and_capture):
    token = lc._request_id_var.set("req-123")
    try:
        logging.getLogger("api.services.some_service").warning("from a child logger")
    finally:
        lc._request_id_var.reset(token)

    record = next(r for r in _factory_and_capture if r.getMessage() == "from a child logger")
    assert record.name == "api.services.some_service" and record.request_id == "req-123"


def test_bound_tenant_user_and_run_identifiers_reach_every_record_and_the_json_line(_factory_and_capture):
    token = lc._log_context_var.set({})
    try:
        lc.bind_log_context(organization_id=uuid.UUID(int=1), user_id="u-9", run_id="run-7")
        logging.getLogger("api.tasks.anything").error("something happened")
    finally:
        lc._log_context_var.reset(token)

    record = next(r for r in _factory_and_capture if r.getMessage() == "something happened")
    assert (record.organization_id, record.user_id, record.run_id) == (str(uuid.UUID(int=1)), "u-9", "run-7")
    line = json.loads(lc.JSONLogFormatter().format(record))
    assert line["organization_id"] == str(uuid.UUID(int=1)) and line["user_id"] == "u-9" and line["run_id"] == "run-7"
    assert "job_id" not in line  # never set: omitted, not null noise


def test_only_known_keys_are_accepted_and_none_is_skipped():
    token = lc._log_context_var.set({})
    try:
        lc.bind_log_context(organization_id="o1", password="hunter2", api_key="sk-secret", user_id=None)
        assert lc.get_log_context() == {"organization_id": "o1"}
    finally:
        lc._log_context_var.reset(token)


def test_outside_a_request_binding_starts_a_context_instead_of_failing():
    assert lc._log_context_var.get() is None
    lc.bind_log_context(job_id="j1")
    try:
        assert lc.get_log_context() == {"job_id": "j1"}
    finally:
        lc._log_context_var.set(None)


async def test_the_middleware_gives_each_request_its_own_context_and_echoes_the_request_id(_factory_and_capture):
    app = FastAPI()
    app.middleware("http")(lc.request_correlation_middleware)

    @app.get("/tenant")
    async def tenant():
        lc.bind_log_context(organization_id="org-A", user_id="user-A")
        logging.getLogger("api.routers.demo").info("inside tenant route")
        return {"ok": True}

    @app.get("/anonymous")
    async def anonymous():
        logging.getLogger("api.routers.demo").info("inside anonymous route")
        return {"ok": True}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = await client.get("/tenant", headers={"X-Request-ID": "rid-1"})
        second = await client.get("/anonymous")

    by_message = {r.getMessage(): r for r in _factory_and_capture}
    assert first.headers["X-Request-ID"] == "rid-1" and by_message["inside tenant route"].request_id == "rid-1"
    assert by_message["inside tenant route"].organization_id == "org-A"
    # the second request must not inherit the first request's tenant or user
    assert by_message["inside anonymous route"].organization_id is None and by_message["inside anonymous route"].user_id is None
    assert by_message["inside anonymous route"].request_id == second.headers["X-Request-ID"] != "rid-1"


async def test_real_org_scoped_requests_bind_the_organization_and_user(monkeypatch, client, db_session, register_payload, _factory_and_capture):
    """The auth dependencies (`get_current_user`, `require_org_member`) bind the context: a log emitted while
    handling a real org-scoped route carries that organization and user."""
    from api.routers import organization_settings as settings_router

    real_get_org_settings = settings_router.get_org_settings

    async def logging_get_org_settings(db, org_id):
        logging.getLogger("api.tests.handler").info("handling the settings request")
        return await real_get_org_settings(db, org_id)

    monkeypatch.setattr(settings_router, "get_org_settings", logging_get_org_settings)
    token = (await client.post("/auth/register", json={"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True})).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Log Org"}, headers={"Authorization": f"Bearer {token}"})).json()["id"]

    await client.get(f"/organizations/{org_id}/settings", headers={"Authorization": f"Bearer {token}"})

    record = next(r for r in _factory_and_capture if r.getMessage() == "handling the settings request")
    assert record.organization_id == org_id
    assert record.user_id is not None and record.request_id is not None
