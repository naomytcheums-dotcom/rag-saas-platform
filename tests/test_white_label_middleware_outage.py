"""A database outage must not turn every request into a 500: the white-label domain lookup runs on every request, so its failure
has to be contained (the health endpoints exist precisely to report that outage)."""

import pytest
from httpx import ASGITransport, AsyncClient

from api.database import get_db
from api.main import app


@pytest.fixture
def database_down():
    async def _broken():
        raise ConnectionRefusedError("database is down")
        yield  # pragma: no cover -- makes this an async generator like the real dependency

    app.dependency_overrides[get_db] = _broken
    yield
    app.dependency_overrides.clear()


async def _get(path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://platform.example") as client:
        return await client.get(path)


async def test_liveness_answers_200_while_the_database_is_down(database_down):
    assert (await _get("/health")).status_code == 200


async def test_the_lookup_failure_leaves_the_request_without_a_tenant(database_down):
    from fastapi import Request

    from api.services.white_label_middleware import white_label_domain_middleware

    seen = {}

    async def call_next(request):
        seen["org"], seen["config"] = request.state.white_label_organization_id, request.state.white_label_config
        return "next"

    scope = {"type": "http", "method": "GET", "path": "/anything", "headers": [(b"host", b"custom.example")], "app": app, "query_string": b""}
    result = await white_label_domain_middleware(Request(scope), call_next)
    assert result == "next" and seen == {"org": None, "config": None}


async def test_health_endpoints_do_not_even_attempt_the_domain_lookup(monkeypatch):
    import api.services.white_label_middleware as middleware

    async def explode(*a, **k):
        raise AssertionError("domain lookup must be skipped for probes")

    monkeypatch.setattr(middleware, "_resolve_custom_domain", explode)
    for path in ("/health", "/health/ready", "/metrics"):
        assert (await _get(path)).status_code == 200
