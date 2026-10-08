"""The public display-currency endpoint: a visitor sees prices in the currency of where they are, with a real (or officially pegged) rate, and
the failure modes fall back to euros instead of guessing."""

import httpx
import pytest

from api.config import settings
from api.services import display_currency
from api.services.display_currency import COUNTRY_CURRENCY, country_from_accept_language, resolve_display_currency

RATES = {"EUR": 1, "USD": 1.08, "JPY": 165.4, "MRU": 43.2, "AED": 3.97}


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    display_currency._cache["rates"] = None
    display_currency._cache["fetched_at"] = 0.0
    monkeypatch.setattr(settings, "DISPLAY_CURRENCY_ENABLED", True)

    async def no_ip_lookup(_ip):
        return None

    monkeypatch.setattr(display_currency, "lookup_country", no_ip_lookup)


def _serve_rates(monkeypatch, payload=None, fail=False):
    calls = {"n": 0}
    original_get = httpx.AsyncClient.get

    async def fake_get(self, url, *args, **kwargs):
        if str(url) != settings.DISPLAY_CURRENCY_RATES_URL:
            return await original_get(self, url, *args, **kwargs)  # the test client's own requests are untouched
        calls["n"] += 1
        if fail:
            raise httpx.ConnectError("rates service down")
        return httpx.Response(200, json=payload or {"result": "success", "rates": RATES}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    return calls


async def _resolve(country=None, ip=None, language=None):
    return await resolve_display_currency(accept_language=language, ip=ip, country_hint=country)


@pytest.mark.parametrize("country,currency", [("US", "USD"), ("JP", "JPY"), ("MR", "MRU"), ("AE", "AED"), ("DE", "EUR"), ("FR", "EUR")])
async def test_every_visitor_gets_the_currency_of_their_country(monkeypatch, country, currency):
    _serve_rates(monkeypatch)
    result = await _resolve(country=country)
    assert result["currency"] == currency
    assert result["country"] == country
    if currency not in ("EUR",):
        assert result["per_euro"] == RATES[currency] and result["source"] == "market"
    else:
        assert result["per_euro"] == 1.0 and result["source"] == "euro"


@pytest.mark.parametrize("country", ["CM", "GA", "SN", "CI"])
async def test_the_cfa_francs_use_the_fixed_official_parity_and_never_call_the_network(monkeypatch, country):
    calls = _serve_rates(monkeypatch)
    result = await _resolve(country=country)
    assert result["currency"] in ("XAF", "XOF")
    assert result["per_euro"] == 655.957 and result["source"] == "peg"
    assert calls["n"] == 0


async def test_the_country_comes_from_the_ip_when_no_hint_is_given(monkeypatch):
    _serve_rates(monkeypatch)

    async def ip_lookup(ip):
        return "JP" if ip == "203.0.113.9" else None

    monkeypatch.setattr(display_currency, "lookup_country", ip_lookup)
    assert (await _resolve(ip="203.0.113.9"))["currency"] == "JPY"


async def test_the_browser_language_region_is_the_last_resort(monkeypatch):
    _serve_rates(monkeypatch)
    assert (await _resolve(language="fr-CM,fr;q=0.9"))["currency"] == "XAF"
    assert country_from_accept_language("en-US,en;q=0.9") == "US"
    assert country_from_accept_language("fr,en") is None


async def test_a_rates_outage_falls_back_to_euros_instead_of_guessing(monkeypatch):
    _serve_rates(monkeypatch, fail=True)
    result = await _resolve(country="JP")
    assert result["currency"] == "EUR" and result["per_euro"] == 1.0


async def test_a_currency_missing_from_the_rates_falls_back_to_euros(monkeypatch):
    _serve_rates(monkeypatch, payload={"rates": {"USD": 1.08}})
    assert (await _resolve(country="JP"))["currency"] == "EUR"


async def test_rates_are_cached_between_visitors(monkeypatch):
    calls = _serve_rates(monkeypatch)
    await _resolve(country="US")
    await _resolve(country="JP")
    await _resolve(country="MR")
    assert calls["n"] == 1


async def test_the_last_good_rates_survive_an_outage(monkeypatch):
    _serve_rates(monkeypatch)
    await _resolve(country="US")
    display_currency._cache["fetched_at"] = 0.0  # expired
    _serve_rates(monkeypatch, fail=True)
    assert (await _resolve(country="US"))["per_euro"] == 1.08


async def test_a_language_is_suggested_for_the_countries_whose_language_we_ship(monkeypatch):
    _serve_rates(monkeypatch)
    for country, language in [("CM", "fr"), ("GA", "fr"), ("DE", "de"), ("MR", "ar"), ("BR", "pt"), ("MX", "es"), ("US", None), ("JP", None)]:
        assert (await _resolve(country=country))["language"] == language


async def test_the_disabled_switch_keeps_everything_in_euros(monkeypatch):
    monkeypatch.setattr(settings, "DISPLAY_CURRENCY_ENABLED", False)
    result = await _resolve(country="JP")
    assert result["currency"] == "EUR"


def test_the_table_covers_the_countries_the_product_cares_about():
    for country in ("MR", "US", "JP", "GA", "DE", "CM", "NG", "ZA", "BR", "IN", "CN", "AE", "GB", "CH"):
        assert country in COUNTRY_CURRENCY


async def test_the_http_endpoint_is_public_and_answers_with_the_documented_shape(client, monkeypatch):
    _serve_rates(monkeypatch)
    response = await client.get("/billing/display-currency?country=us")
    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "USD" and body["country"] == "US" and body["per_euro"] == 1.08
    assert (await client.get("/billing/display-currency?country=zzzz")).status_code == 422
