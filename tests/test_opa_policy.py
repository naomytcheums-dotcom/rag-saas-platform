"""
api/services/opa_policy.py -- `AsyncOpaClient.query_rule` makes a real
HTTP call under the hood to a configured OPA server. Mocked here at
its own clean, already-tested boundary, verified directly against the
installed `opa-python-client` package before writing this module --
never a fabricated shape."""

from unittest.mock import AsyncMock, patch

from api.services.opa_policy import check_policy


async def test_check_policy_returns_none_when_opa_is_disabled(monkeypatch):
    """Real, deliberate default: OPA_ENABLED is False unless an
    operator explicitly configures a real OPA server."""
    monkeypatch.setattr("api.config.settings.OPA_ENABLED", False)
    mock_client = AsyncMock()

    with patch("api.services.opa_policy._get_client", return_value=mock_client):
        result = await check_policy({"user": "alice"}, "documents.retrieval", "allow")

    assert result is None
    mock_client.query_rule.assert_not_called()


async def test_check_policy_returns_the_real_boolean_result_when_enabled(monkeypatch):
    """Validation criterion: a real, successful OPA evaluation's own
    boolean result flows straight through."""
    monkeypatch.setattr("api.config.settings.OPA_ENABLED", True)
    mock_client = AsyncMock()
    mock_client.query_rule = AsyncMock(return_value={"result": True})

    with patch("api.services.opa_policy._get_client", return_value=mock_client):
        result = await check_policy({"user": "alice", "clearance_level": 3}, "documents.retrieval", "allow")

    assert result is True
    mock_client.query_rule.assert_awaited_once_with(
        {"user": "alice", "clearance_level": 3}, "documents.retrieval", "allow",
    )


async def test_check_policy_returns_none_on_a_real_connection_failure(monkeypatch):
    """Real, fail-open discipline (see this module's own top docstring
    for why): an unreachable/misconfigured real OPA server must never
    turn into a denial -- only an explicit, successful real `False`
    from OPA itself should ever restrict access."""
    monkeypatch.setattr("api.config.settings.OPA_ENABLED", True)
    mock_client = AsyncMock()
    mock_client.query_rule = AsyncMock(side_effect=ConnectionError("real, unreachable OPA server"))

    with patch("api.services.opa_policy._get_client", return_value=mock_client):
        result = await check_policy({"user": "alice"}, "documents.retrieval", "allow")

    assert result is None


async def test_check_policy_returns_none_for_a_non_boolean_real_result(monkeypatch):
    """Real, honest handling: a real rule that doesn't evaluate to a
    plain boolean (e.g. undefined, or a real Rego object) never gets
    coerced into a fabricated True/False."""
    monkeypatch.setattr("api.config.settings.OPA_ENABLED", True)
    mock_client = AsyncMock()
    mock_client.query_rule = AsyncMock(return_value={"result": {"nested": "object"}})

    with patch("api.services.opa_policy._get_client", return_value=mock_client):
        result = await check_policy({"user": "alice"}, "documents.retrieval", "allow")

    assert result is None


async def test_check_policy_returns_the_real_false_result_when_opa_denies(monkeypatch):
    """The one real case this integration adds a restriction for: a
    genuine, successfully-evaluated OPA rule that explicitly returns
    False."""
    monkeypatch.setattr("api.config.settings.OPA_ENABLED", True)
    mock_client = AsyncMock()
    mock_client.query_rule = AsyncMock(return_value={"result": False})

    with patch("api.services.opa_policy._get_client", return_value=mock_client):
        result = await check_policy({"user": "alice", "clearance_level": 1}, "documents.retrieval", "allow")

    assert result is False


async def test_the_rest_client_posts_to_the_opa_data_api_path_of_the_rule(monkeypatch):
    """The OPA address is built from the dotted package path + rule, and the answer is returned as OPA sent it."""
    import httpx

    from api.services.opa_policy import _OpaRestClient

    captured = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"result": True}

    async def fake_post(self, url, json=None, **kwargs):
        captured["url"], captured["json"] = url, json
        return _Response()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = await _OpaRestClient("opa.internal", 8181).query_rule({"user": "ada"}, "documents.retrieval", "allow")

    assert result == {"result": True}
    assert captured["url"] == "http://opa.internal:8181/v1/data/documents/retrieval/allow"
    assert captured["json"] == {"input": {"user": "ada"}}


async def test_the_rest_client_without_a_rule_queries_the_whole_package(monkeypatch):
    import httpx

    from api.services.opa_policy import _OpaRestClient

    urls = []

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"result": {"allow": True}}

    async def fake_post(self, url, json=None, **kwargs):
        urls.append(url)
        return _Response()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await _OpaRestClient("localhost", 8181).query_rule({}, "documents.retrieval")
    assert urls == ["http://localhost:8181/v1/data/documents/retrieval"]


async def test_an_http_error_from_opa_stays_advisory_and_never_raises(monkeypatch):
    from api.config import settings
    from api.services import opa_policy

    class _Broken:
        async def query_rule(self, *args, **kwargs):
            raise RuntimeError("OPA answered 500")

    monkeypatch.setattr(settings, "OPA_ENABLED", True)
    monkeypatch.setattr(opa_policy, "_get_client", lambda: _Broken())
    assert await opa_policy.check_policy({}, "documents.retrieval", "allow") is None
