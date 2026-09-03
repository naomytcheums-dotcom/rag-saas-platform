"""
Partie 2.1.10 -- fetching a user-supplied URL for real, safely.

**This is a genuinely different threat model from every prior 2.1.x
step**: PDF/DOCX/.../EPUB all process bytes the caller already
uploaded -- this codebase never chooses to go fetch anything on its
own. Importing "a page at this URL" means THIS SERVER makes an
outbound HTTP request to an address the caller controls -- textbook
SSRF (OWASP A10:2021) territory if the target can be an internal
service, a cloud metadata endpoint, or anything else this server can
reach that the caller couldn't reach directly. Vision critique Q2 asks
for this directly; the answer here is real infrastructure, not a
hostname string blocklist.

**Real, deliberate architecture, verified before writing production
code**: every real network connection this module makes goes through
`_SSRFSafeAsyncTransport`, an `httpx.AsyncHTTPTransport` whose
underlying `httpcore` connection pool is given a CUSTOM network
backend (`_SSRFSafeBackend`, overriding `connect_tcp`) that resolves
the target hostname itself via `socket.getaddrinfo` and validates the
resulting IP BEFORE connecting -- confirmed for real to correctly
block a direct request to a private/loopback/link-local address, AND
(a strictly harder, and more important, case) a request that
INITIALLY resolves safely but then 30x-redirects to one: httpx
re-invokes `connect_tcp` for every new host in a redirect chain, so
each hop is independently validated at the moment of connecting, not
just the one the caller originally typed -- this is what actually
defeats a classic "safe URL that redirects to 127.0.0.1" SSRF attempt,
confirmed for real against a live redirect. Validating the ORIGINAL
url's hostname once and then trusting the connection (a naive, common
mistake) would NOT catch this.

**Real finding, and why this is `ip.is_global`, not a hand-rolled
`is_private or is_loopback or ...` blocklist**: an early version of
this check used Python's `ipaddress.ip_address(...).is_private`
directly -- confirmed for real to MISS `100.64.0.0/10` (RFC 6598's
"Shared Address Space", real carrier-grade-NAT address space some
cloud/ISP internal networks genuinely route) -- `is_private` returns
`False` for it. `is_global` (an allowlist -- "is this address real,
routable, public internet space" -- rather than a blocklist of known-
bad ranges) correctly excludes it, along with every other case
`is_private`/`is_loopback`/`is_link_local`/`is_reserved`/
`is_unspecified` already covered (loopback, RFC 1918 private ranges,
link-local/cloud-metadata's own 169.254.0.0/16, IPv4-mapped IPv6
loopback like `::ffff:127.0.0.1`, unspecified `0.0.0.0`/`::`, IPv6 ULA
`fc00::/7`). A DEFAULT-DENY allowlist is the correct shape for a
security check like this, not a default-allow blocklist that has to
enumerate every bad range correctly (and, confirmed for real above,
can genuinely miss one). The one real gap `is_global` itself has: a
multicast address (e.g. `224.0.0.1`) reports `is_global=True` -- an
explicit `not ip.is_multicast` check closes it.

**Real, transparent User-Agent, not a spoofed browser one** -- this
server identifies itself honestly as what it is (an automated
importer), the same ethical default real crawlers use, and the
identity `validate_url_robots_txt` below checks robots.txt rules
against.

**Response size is capped while streaming** (`MAX_DOCUMENT_UPLOAD_BYTES`,
the SAME limit every uploaded file already has -- `api/services/
document_storage.py`), not just a `Content-Length` header check (a
server can omit or lie about it) -- real bytes are counted as they
arrive, and the fetch aborts the moment the real cap would be exceeded.
"""

import ipaddress
import socket
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from httpcore._backends.anyio import AnyIOBackend

from api.services.document_storage import MAX_DOCUMENT_UPLOAD_BYTES

USER_AGENT = "RAGSaaSPlatform-DocumentImporter/0.1"
_ALLOWED_SCHEMES = ("http", "https")
_CONNECT_TIMEOUT = 10.0
_READ_TIMEOUT = 20.0


def _is_safe_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return ip.is_global and not ip.is_multicast


def _resolve_safe_ip(host: str, port: int) -> str:
    """Real DNS resolution (not string-matching the hostname) -- a
    hostname's OWN string never tells you what it resolves to; only a
    real lookup does. Raises ValueError, caught the same way every
    other format's own real validation failure is, if resolution fails
    outright or every resolved address is disallowed."""
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"could not resolve host {host!r}: {exc}") from exc
    candidates = [info[4][0] for info in infos]
    safe = [ip for ip in candidates if _is_safe_ip(ip)]
    if not safe:
        raise ValueError(f"host {host!r} does not resolve to a real, public address (resolved: {candidates})")
    return safe[0]


class _SSRFSafeBackend(AnyIOBackend):
    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        safe_ip = _resolve_safe_ip(host, port)
        return await super().connect_tcp(safe_ip, port, timeout=timeout, local_address=local_address, socket_options=socket_options)


class _SSRFSafeAsyncTransport(httpx.AsyncHTTPTransport):
    """See this module's own docstring for the full real design. httpx
    does not expose a `network_backend` constructor argument on
    `AsyncHTTPTransport` itself (confirmed for real against the
    installed httpx version) -- the underlying httpcore connection
    pool it builds internally does, so this replaces that pool's
    backend post-construction, the smallest real change that achieves
    the SSRF-safe connection behavior above."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._pool._network_backend = _SSRFSafeBackend()


def _client() -> httpx.AsyncClient:
    """One shared client configuration for every real network call in
    this module -- one place the SSRF-safe transport is wired in, not
    several call sites that could each independently forget it."""
    return httpx.AsyncClient(
        transport=_SSRFSafeAsyncTransport(),
        timeout=httpx.Timeout(connect=_CONNECT_TIMEOUT, read=_READ_TIMEOUT, write=_READ_TIMEOUT, pool=_CONNECT_TIMEOUT),
        follow_redirects=True,
        max_redirects=5,
        headers={"User-Agent": USER_AGENT},
    )


def validate_url(url: str) -> str:
    """Item 3's literal function -- real, PURE format/scheme validation,
    zero network I/O (see this module's own docstring on why the real
    SSRF check lives at the connection layer instead, only ever
    reached once real network activity actually starts). Returns the
    normalized URL string. Rejects: a missing/disallowed scheme (only
    `http`/`https`, vision critique Q2's own literal ask -- no `file:`,
    `ftp:`, `gopher:`, `data:`, ...), a missing hostname, and embedded
    userinfo (`http://user:pass@host/`) -- a real, documented URL-
    parsing confusion vector, not a legitimate feature this importer
    needs to support.
    """
    parts = urlsplit(url.strip())
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"URL scheme must be one of {_ALLOWED_SCHEMES}, got {parts.scheme!r}")
    if not parts.hostname:
        raise ValueError("URL has no hostname")
    if parts.username or parts.password:
        raise ValueError("URL must not contain embedded credentials")
    return parts.geturl()


async def validate_url_accessibility(url: str) -> None:
    """Item 3's literal function -- a real HEAD request (falling back
    to a real, minimally-streamed GET for the real servers, confirmed
    to exist, that reject HEAD with 405) through the SAME SSRF-safe
    transport every other real request in this module uses. Raises
    ValueError for a non-200 status or any real connection failure --
    vision critique Q3's own "inaccessible URL" answer."""
    async with _client() as client:
        try:
            response = await client.head(url)
            if response.status_code == 200:
                return
            if response.status_code not in (405, 501):
                raise ValueError(f"URL returned HTTP {response.status_code}, expected 200")
        except httpx.HTTPError as exc:
            raise ValueError(f"URL is not accessible: {exc}") from exc

        try:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise ValueError(f"URL returned HTTP {response.status_code}, expected 200")
        except httpx.HTTPError as exc:
            raise ValueError(f"URL is not accessible: {exc}") from exc


async def validate_url_robots_txt(url: str) -> None:
    """Item 3's literal (optional) function -- real robots.txt handling,
    the same real convention actual crawlers use: a robots.txt that is
    missing, unreachable, or itself fails to fetch is treated as
    "allowed" (a site with no stated preference has no preference to
    honor), but a robots.txt that is REACHED and explicitly disallows
    this real, transparent User-Agent (or `*`) for this path raises a
    real ValueError -- this importer respects a site's stated
    preference rather than ignoring it because the check is optional
    to have at all.
    """
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    async with _client() as client:
        try:
            response = await client.get(robots_url)
        except httpx.HTTPError:
            return
    if response.status_code != 200:
        return

    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    if not parser.can_fetch(USER_AGENT, url):
        raise ValueError(f"'{url}' is disallowed by {robots_url}")


async def fetch_url_content(url: str) -> tuple[bytes, str]:
    """Item 2's literal function -- real bytes (streamed, capped at
    MAX_DOCUMENT_UPLOAD_BYTES -- see this module's own docstring) and
    the real FINAL url reached after following redirects (the caller's
    original url may not be where the real content actually lives)."""
    async with _client() as client:
        try:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise ValueError(f"URL returned HTTP {response.status_code}, expected 200")
                chunks = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_DOCUMENT_UPLOAD_BYTES:
                        raise ValueError(f"URL content exceeds the {MAX_DOCUMENT_UPLOAD_BYTES // (1024 * 1024)}MB limit")
                    chunks.append(chunk)
                return b"".join(chunks), str(response.url)
        except httpx.HTTPError as exc:
            raise ValueError(f"failed to fetch '{url}': {exc}") from exc
