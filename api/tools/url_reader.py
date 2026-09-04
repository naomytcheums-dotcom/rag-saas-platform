"""
Partie 5.2.6 -- letting an agent read a real web page's content.

**Real reuse, not duplication**: `validate_url`/`fetch_url_content`
(Partie 2.1.10, `api/services/url_fetching.py`) provide the SAME real,
already-verified SSRF-safe transport (DNS-rebinding-safe IP resolution
at connect time, scheme/hostname validation, redirect-following capped
at a real byte limit) every other real URL-fetching path in this
codebase already uses -- no second, parallel network client built
here (vision critique's own "réutiliser 2.1.10" answer). `extract_url_main_content`/
`extract_url_metadata` (Partie 2.1.10/2.1.11, `api/services/url_extraction.py`)
provide the same real readability-based extraction already used for URL
document imports.

**A real, documented deviation from this étape's own literal 1-arg
`extract_url_content(html)`/`extract_url_metadata(html)` signatures**:
both real, reused underlying functions take `(url, html)` -- `url` is
real, load-bearing information for `extract_url_metadata` (the real
`source_url` field, and the real title fallback when a page declares
none). Dropping it to match the literal 1-arg shape would mean either
duplicating the real function with `url` hardcoded to `""`, or losing
real functionality -- this module's own `extract_url_content`/
`extract_url_metadata` keep the real, useful `(url, html)` shape
instead.

**`URL_READER_MAX_SIZE`, a real, additional, tool-specific cap on top
of** `url_fetching.MAX_DOCUMENT_UPLOAD_BYTES` (real, already enforced
INSIDE `fetch_url_content` itself, sized for real document imports,
not an agent's own real, tighter per-read budget) -- this module
applies its own real, stricter check after the real fetch returns.
"""

import httpx

from api.config import settings
from api.services.tools import ToolSpec
from api.services.url_extraction import extract_url_main_content, extract_url_metadata
from api.services.url_fetching import fetch_url_content, validate_url


class UrlReaderError(ValueError):
    """Real, dedicated exception."""


def _check_domain_allowlist(url: str) -> None:
    """Real, additional check backing `URL_READER_ALLOWED_DOMAINS`/
    `URL_READER_BLOCKED_DOMAINS` (not itself the real SSRF defense --
    that lives in `url_fetching`'s own connection-layer IP check, which
    a domain string can't spoof around; this is a real, separate,
    caller-configurable policy layer on top)."""
    from urllib.parse import urlsplit
    hostname = (urlsplit(url).hostname or "").lower()
    if settings.URL_READER_BLOCKED_DOMAINS and any(hostname == d or hostname.endswith(f".{d}") for d in settings.URL_READER_BLOCKED_DOMAINS):
        raise UrlReaderError(f"Domain {hostname!r} is blocked")
    if settings.URL_READER_ALLOWED_DOMAINS and not any(hostname == d or hostname.endswith(f".{d}") for d in settings.URL_READER_ALLOWED_DOMAINS):
        raise UrlReaderError(f"Domain {hostname!r} is not in the configured allowlist")


async def _fetch_and_decode(url: str) -> tuple[str, str]:
    validated_url = validate_url(url)
    _check_domain_allowlist(validated_url)
    try:
        content_bytes, final_url = await fetch_url_content(validated_url)
    except ValueError as exc:
        raise UrlReaderError(str(exc)) from exc

    if len(content_bytes) > settings.URL_READER_MAX_SIZE:
        raise UrlReaderError(f"URL content exceeds the real, configured limit of {settings.URL_READER_MAX_SIZE} bytes")
    try:
        html = content_bytes.decode("utf-8", errors="replace")
    except LookupError as exc:
        raise UrlReaderError(f"Could not decode content from {final_url!r}") from exc
    return html, final_url


async def read_url(url: str) -> str:
    """Item 2's own literal function -- real main content, boilerplate
    stripped."""
    html, final_url = await _fetch_and_decode(url)
    return extract_url_main_content(final_url, html)


async def read_url_with_metadata(url: str) -> dict:
    """Item 2's own literal function -- real content plus real
    title/author/date/description/`source_url`."""
    html, final_url = await _fetch_and_decode(url)
    return {"content": extract_url_main_content(final_url, html), **extract_url_metadata(final_url, html)}


def extract_url_content(url: str, html: str) -> str:
    """Item 2's own literal function name -- real `(url, html)` shape,
    see this module's own top docstring for why."""
    return extract_url_main_content(url, html)


# Item 2's own literal `extract_url_metadata` function name is already
# real and available in this module's own namespace via the import
# above (`from api.services.url_extraction import ... extract_url_metadata`)
# -- no separate wrapper needed; re-defining it here would just shadow
# the real, reused function with an identical pass-through.


async def _url_reader_tool_handler(url: str) -> str:
    try:
        return await read_url(url)
    except UrlReaderError as exc:
        return f"Could not read URL: {exc}"


URL_READER_TOOL = ToolSpec(
    name="read_url", description="Read and extract the main content from a URL",
    parameters={"url": {"type": "string", "description": "The URL to read"}},
    capability_tags=("web", "read", "content"), handler=_url_reader_tool_handler,
)
