"""Sensitive settings fail SAFE (Lot F): defaults of the six settings named by the audit, and /metrics fail-closed mode.
Documented in docs/devops/SENSITIVE_SETTINGS.md (development / test / production modes)."""

from api.config import Settings, settings


def _default(name):
    return Settings.model_fields[name].default


def test_the_money_and_exposure_settings_default_to_the_safe_value():
    assert _default("CREDITS_ALLOW_UNPAID_TOPUP") is False      # no free credits
    assert _default("BILLING_ALLOW_SELF_SERVICE_PAID_PLANS") is False  # an organization cannot give itself a paid plan or mark an invoice paid
    assert _default("COOKIE_SECURE") is True                    # cookies only over TLS
    assert _default("MCP_STDIO_ENABLED") is False               # no OS command from a tenant-configured MCP server
    assert _default("METRICS_REQUIRE_AUTH") is False            # historical behaviour kept; opt in to fail closed


def test_the_documented_open_by_default_settings_are_exactly_these():
    """These two are open/off by default ON PURPOSE (private-network scraper, optional antivirus); the test pins them so a change is visible."""
    assert _default("METRICS_AUTH_TOKEN") is None
    assert _default("CLAMAV_ENABLED") is False


async def test_metrics_stay_open_by_default_without_a_token(client, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_AUTH_TOKEN", None)
    monkeypatch.setattr(settings, "METRICS_REQUIRE_AUTH", False)
    assert (await client.get("/metrics")).status_code == 200


async def test_metrics_fail_closed_when_auth_is_required_but_no_token_is_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_AUTH_TOKEN", None)
    monkeypatch.setattr(settings, "METRICS_REQUIRE_AUTH", True)
    response = await client.get("/metrics")
    assert response.status_code == 503 and "METRICS_AUTH_TOKEN" in response.text and "process_" not in response.text


async def test_metrics_with_a_token_still_demand_it_in_both_modes(client, monkeypatch):
    for require in (False, True):
        monkeypatch.setattr(settings, "METRICS_AUTH_TOKEN", "scrape-token-value")
        monkeypatch.setattr(settings, "METRICS_REQUIRE_AUTH", require)
        assert (await client.get("/metrics")).status_code == 401
        assert (await client.get("/metrics", headers={"Authorization": "Bearer scrape-token-value"})).status_code == 200
