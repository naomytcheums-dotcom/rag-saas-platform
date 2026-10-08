"""Which currency (and language) a visitor should see, from where they are in the world.

Plans are stored and billed in euros; this only decides how an amount is DISPLAYED. The country comes, in order, from an explicit hint (the browser's
own time zone / locale, sent by the page), the caller's IP address (api/security/geoip.py), then the browser language region. The currency is the
country's official one. The euro rate comes from a free public rates service, cached for a few hours; the CFA / CFP / Comorian francs are pegged to
the euro by treaty, so those use the fixed official rate and never depend on the network.

Everything fails safe: an unknown country, an unreachable rates service or a currency the service does not list all fall back to euros, never to an
error and never to a made-up rate.
"""

import asyncio
import logging
import re
import time

import httpx

from api.config import settings
from api.security.geoip import lookup_country

logger = logging.getLogger(__name__)

# Official fixed parities with the euro (units of the currency for one euro).
PEGGED_PER_EUR: dict[str, float] = {"XAF": 655.957, "XOF": 655.957, "KMF": 491.96775, "XPF": 119.331742}

# Official currency of each country, written as currency -> countries to keep the table short and reviewable.
_CURRENCY_COUNTRIES: dict[str, str] = {
    "EUR": "AT BE CY DE EE ES FI FR GR HR IE IT LT LU LV MT NL PT SI SK AD MC SM VA ME XK AX BL GF GP MF MQ PM RE TF YT",
    "USD": "US EC SV PR GU AS MP VI TL PW FM MH PA ZW BQ IO TC VG UM",
    "GBP": "GB GG IM JE", "CHF": "CH LI", "JPY": "JP", "CNY": "CN", "HKD": "HK", "TWD": "TW", "KRW": "KR", "INR": "IN", "IDR": "ID", "SGD": "SG",
    "MYR": "MY", "THB": "TH", "VND": "VN", "PHP": "PH", "PKR": "PK", "BDT": "BD", "LKR": "LK", "NPR": "NP", "KHR": "KH", "MMK": "MM", "LAK": "LA",
    "MNT": "MN", "KZT": "KZ", "UZS": "UZ", "AUD": "AU KI NR TV", "NZD": "NZ CK NU TK", "FJD": "FJ", "PGK": "PG", "CAD": "CA", "MXN": "MX",
    "BRL": "BR", "ARS": "AR", "CLP": "CL", "COP": "CO", "PEN": "PE", "UYU": "UY", "PYG": "PY", "BOB": "BO", "VES": "VE", "GTQ": "GT", "HNL": "HN",
    "NIO": "NI", "CRC": "CR", "DOP": "DO", "JMD": "JM", "TTD": "TT", "HTG": "HT", "CUP": "CU", "BSD": "BS", "BBD": "BB", "BZD": "BZ", "XCD": "AG DM GD KN LC VC AI MS",
    "SEK": "SE", "NOK": "NO SJ", "DKK": "DK FO GL", "ISK": "IS", "PLN": "PL", "CZK": "CZ", "HUF": "HU", "RON": "RO", "BGN": "BG", "RSD": "RS", "UAH": "UA",
    "TRY": "TR", "RUB": "RU", "BYN": "BY", "GEL": "GE", "AMD": "AM", "AZN": "AZ", "MDL": "MD", "ALL": "AL", "MKD": "MK", "BAM": "BA",
    "ILS": "IL PS", "AED": "AE", "SAR": "SA", "QAR": "QA", "KWD": "KW", "BHD": "BH", "OMR": "OM", "JOD": "JO", "LBP": "LB", "IQD": "IQ", "IRR": "IR",
    "EGP": "EG", "MAD": "MA EH", "DZD": "DZ", "TND": "TN", "LYD": "LY", "MRU": "MR", "NGN": "NG", "GHS": "GH", "KES": "KE", "TZS": "TZ", "UGX": "UG",
    "RWF": "RW", "ETB": "ET", "ZAR": "ZA", "NAD": "NA", "BWP": "BW", "MZN": "MZ", "ZMW": "ZM", "AOA": "AO", "MGA": "MG", "MUR": "MU", "SCR": "SC",
    "CDF": "CD", "BIF": "BI", "GNF": "GN", "SLE": "SL", "LRD": "LR", "GMD": "GM", "SDG": "SD", "SSP": "SS", "SOS": "SO", "DJF": "DJ", "ERN": "ER",
    "MWK": "MW", "LSL": "LS", "SZL": "SZ", "CVE": "CV", "STN": "ST",
    "XAF": "CM GA CG TD CF GQ", "XOF": "SN CI ML BF BJ TG NE GW", "KMF": "KM", "XPF": "PF NC WF",
}
COUNTRY_CURRENCY: dict[str, str] = {country: currency for currency, countries in _CURRENCY_COUNTRIES.items() for country in countries.split()}

# Languages the interface ships (en, fr, es, de, pt, ar) -> the country's most useful one. Unlisted countries stay in English.
_LANGUAGE_COUNTRIES: dict[str, str] = {
    "fr": "FR BE LU MC CM GA CG CD TD CF GQ SN CI ML BF BJ TG NE GN DJ MG BI RW HT KM SC GP MQ GF RE YT PM PF NC WF BL MF TF",
    "es": "ES MX AR CL CO PE VE EC GT CU BO DO HN PY SV NI CR PA UY PR",
    "de": "DE AT LI",
    "pt": "PT BR AO MZ CV GW ST TL",
    "ar": "SA AE QA KW BH OM JO LB IQ SY YE EG LY DZ MA TN MR SD SO PS",
}
COUNTRY_LANGUAGE: dict[str, str] = {country: language for language, countries in _LANGUAGE_COUNTRIES.items() for country in countries.split()}

_cache: dict[str, object] = {"rates": None, "fetched_at": 0.0}
_lock = asyncio.Lock()


def _clean_country(value: str | None) -> str | None:
    code = (value or "").strip().upper()
    return code if re.fullmatch(r"[A-Z]{2}", code) else None


def country_from_accept_language(header: str | None) -> str | None:
    """`fr-CM,fr;q=0.9,en;q=0.8` -> CM (the region of the first language tag that has one)."""
    for part in (header or "").split(","):
        tag = part.split(";")[0].strip()
        match = re.fullmatch(r"[A-Za-z]{2,3}[-_]([A-Za-z]{2})", tag)
        if match:
            return match.group(1).upper()
    return None


async def _market_rates() -> dict[str, float] | None:
    """EUR -> {currency: units per euro}, cached; the previous value is kept when the service is unreachable."""
    now = time.time()
    cached = _cache["rates"]
    if cached and now - float(_cache["fetched_at"]) < settings.DISPLAY_CURRENCY_RATES_TTL_SECONDS:
        return cached  # type: ignore[return-value]
    async with _lock:
        if _cache["rates"] and time.time() - float(_cache["fetched_at"]) < settings.DISPLAY_CURRENCY_RATES_TTL_SECONDS:
            return _cache["rates"]  # type: ignore[return-value]
        try:
            async with httpx.AsyncClient(timeout=settings.DISPLAY_CURRENCY_TIMEOUT_SECONDS) as http_client:
                response = await http_client.get(settings.DISPLAY_CURRENCY_RATES_URL)
            response.raise_for_status()
            body = response.json()
            rates = body.get("rates") if isinstance(body, dict) else None
            if not isinstance(rates, dict) or not rates:
                raise ValueError("no rates in the response")
            _cache["rates"] = {str(code): float(rate) for code, rate in rates.items() if isinstance(rate, (int, float)) and rate > 0}
            _cache["fetched_at"] = time.time()
        except Exception as exc:  # noqa: BLE001 -- any failure means "keep the last good rates, or fall back to euros"
            logger.warning("display-currency rates unavailable: %s", exc)
        return _cache["rates"]  # type: ignore[return-value]


async def resolve_display_currency(*, accept_language: str | None, ip: str | None, country_hint: str | None) -> dict:
    """Country, currency, units-per-euro and a language suggestion for one visitor."""
    country = _clean_country(country_hint)
    if country is None and settings.DISPLAY_CURRENCY_ENABLED:
        country = await lookup_country(ip)
    if country is None:
        country = country_from_accept_language(accept_language)

    language = COUNTRY_LANGUAGE.get(country or "", None)
    currency = COUNTRY_CURRENCY.get(country or "", "EUR")
    result = {"country": country, "currency": "EUR", "per_euro": 1.0, "source": "euro", "attribution_url": None, "language": language}
    if currency == "EUR" or not settings.DISPLAY_CURRENCY_ENABLED:
        return result

    if currency in PEGGED_PER_EUR:
        return {**result, "currency": currency, "per_euro": PEGGED_PER_EUR[currency], "source": "peg"}

    rates = await _market_rates()
    rate = rates.get(currency) if rates else None
    if not rate:
        return result  # unknown or unavailable: show euros rather than guess
    return {**result, "currency": currency, "per_euro": round(rate, 6), "source": "market", "attribution_url": settings.DISPLAY_CURRENCY_ATTRIBUTION_URL}
