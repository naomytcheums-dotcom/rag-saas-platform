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
