"""Shared HTTP call for the OAuth-protected vendor APIs of the agent tools (Google Calendar, Microsoft Graph, Gmail).

What it adds on top of a bare `client.request(...).raise_for_status()`:
- a 401 (access token revoked or expired before its announced lifetime) invalidates the cached token and retries ONCE with a fresh one;
- 429 is retried with the vendor's Retry-After (bounded), since the vendor says the request was not processed;
- 5xx are retried only for idempotent reads (GET): replaying a POST /send after a 502 could deliver the same e-mail twice;
- every failure surfaces as the tool's own error class with the vendor's message, never as a raw httpx exception and never with the token in it.
"""

import asyncio
from collections.abc import Awaitable, Callable

import httpx

_MAX_RETRIES = 2
_MAX_RETRY_AFTER_SECONDS = 5.0
_IDEMPOTENT_METHODS = {"GET", "HEAD"}


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    try:
        return min(max(float(response.headers.get("retry-after", "")), 0.0), _MAX_RETRY_AFTER_SECONDS)
    except ValueError:
        return min(0.5 * 2**attempt, _MAX_RETRY_AFTER_SECONDS)


def vendor_message(response: httpx.Response) -> str:
    """The vendor's own explanation (Google `error.message`, Graph `error.message`, OAuth `error_description`), shortened."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or error)[:300]
        if error:
            return str(body.get("error_description") or error)[:300]
    return response.text[:300]


def token_refresh_error(response: httpx.Response) -> str:
    """"invalid_grant): Token has been expired or revoked" -- the OAuth error code and description of a failed refresh."""
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    return f"{body.get('error', 'unknown_error')}): {body.get('error_description', response.text[:300])}"


async def oauth_request(
    client_factory: Callable[[], httpx.AsyncClient],
    method: str,
    url: str,
    *,
    authenticate: Callable[[], Awaitable[str]],
    invalidate: Callable[[], None],
    error_cls: type[Exception],
    label: str,
    **request_kwargs,
) -> httpx.Response:
    token = await authenticate()
    refreshed = False
    attempt = 0
    while True:
        try:
            async with client_factory() as client:
                response = await client.request(method, url, headers={"Authorization": f"Bearer {token}"}, **request_kwargs)
        except httpx.TimeoutException as exc:
            raise error_cls(f"{label} did not answer in time") from exc
        except httpx.RequestError as exc:
            raise error_cls(f"could not reach {label}: {type(exc).__name__}") from exc
        status = response.status_code
        if status == 401 and not refreshed:
            invalidate()
            token = await authenticate()
            refreshed = True
            continue
        retryable = status == 429 or (status in (500, 502, 503, 504) and method.upper() in _IDEMPOTENT_METHODS)
        if retryable and attempt < _MAX_RETRIES:
            await asyncio.sleep(_retry_delay(response, attempt))
            attempt += 1
            continue
        if status >= 400:
            raise error_cls(f"{label} API error {status}: {vendor_message(response)}")
        return response
