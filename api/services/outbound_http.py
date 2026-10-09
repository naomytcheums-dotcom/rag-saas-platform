"""Outbound HTTP for tenant-configured URLs (webhooks, MCP servers): SSRF-safe by construction (SEC-005).

A tenant owner can point a webhook or an MCP server at any URL, so the worker/API must never be a way into private networks
(cloud metadata, internal services, loopback). Two layers, mirroring `api/services/url_fetching.py`:

* `validate_outbound_url` -- cheap, syntactic and offline (scheme, host present, no credentials, no literal private IP / localhost),
  used when a URL is configured so that obvious abuse is a 4xx instead of a failed delivery later;
* connection-time resolution -- the authoritative check: the hostname is resolved by the network backend itself and every
  resolved address must be public (`ip.is_global`) before any socket is opened, for every redirect hop and every retry, so a
  hostname that later resolves to a private address (DNS rebinding) is refused as well.

`OUTBOUND_PRIVATE_HOST_ALLOWLIST` (empty by default) lets a self-hosted installation reach specific internal webhook receivers or
MCP servers. Error text never includes resolved addresses or remote error messages: `describe_outbound_error` returns a short,
fixed description, because these messages end up in database columns that tenants can read."""

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlsplit

import httpx
from httpcore._backends.sync import SyncBackend

from api.config import settings

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = ("http", "https")
_MAX_URL_LENGTH = 2048
_LOCAL_NAMES = ("localhost",)


class OutboundURLError(ValueError):
    """The destination is not an acceptable public address. The message is fixed text: it never echoes what was resolved."""


def _allowlist() -> tuple[set[str], list[ipaddress.IPv4Network | ipaddress.IPv6Network]]:
    """Operator-configured exceptions: exact host names and IP addresses/CIDR ranges (comma separated)."""
    names: set[str] = set()
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in (settings.OUTBOUND_PRIVATE_HOST_ALLOWLIST or "").split(","):
        entry = entry.strip().lower().rstrip(".")
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            names.add(entry)
    return names, networks


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return ip.is_global and not ip.is_multicast


def _is_allowlisted(host: str, ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None) -> bool:
    names, networks = _allowlist()
    if host.lower().rstrip(".") in names:
        return True
    return ip is not None and any(ip in network for network in networks)


def validate_outbound_url(url: str) -> str:
    """Offline validation of a configured URL; returns it unchanged. Raises ValueError with a user-safe message."""
    if not isinstance(url, str) or not url.strip() or len(url) > _MAX_URL_LENGTH:
        raise ValueError("url must be a non-empty http(s) URL of at most 2048 characters")
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname
        parts.port  # noqa: B018 -- raises ValueError for a malformed or out-of-range port
    except ValueError as exc:
        raise ValueError("url is not a valid http(s) URL") from exc
    if parts.scheme.lower() not in _ALLOWED_SCHEMES or not host:
        raise ValueError("url must use http or https and name a host")
    if parts.username is not None or parts.password is not None:
        raise ValueError("url must not contain credentials")
    host = host.lower().rstrip(".")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    local_name = host in _LOCAL_NAMES or host.endswith(".localhost")
    if (literal is not None and not _is_public(literal) and not _is_allowlisted(host, literal)) or (
        local_name and not _is_allowlisted(host, None)
    ):
        raise ValueError("url must point to a public host")
    return url


def _resolve_outbound_ip(host: str, port: int) -> str:
    """Resolve `host` now and return one address that is public (or explicitly allowlisted); never raises anything but OutboundURLError."""
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise OutboundURLError("destination could not be resolved") from exc
    for info in infos:
        candidate = info[4][0]
        try:
            ip = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if _is_public(ip) or _is_allowlisted(host, ip):
            return candidate
    raise OutboundURLError("destination is not a public address")


class _SafeSyncBackend(SyncBackend):
    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        return super().connect_tcp(_resolve_outbound_ip(host, port), port, timeout=timeout, local_address=local_address, socket_options=socket_options)


class _SafeSyncTransport(httpx.HTTPTransport):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._pool._network_backend = _SafeSyncBackend()


def safe_webhook_client(timeout: float) -> httpx.Client:
    """Synchronous client for the Celery webhook task. Redirects are not followed: a delivery is one request to the configured URL."""
    return httpx.Client(transport=_SafeSyncTransport(), timeout=timeout, follow_redirects=False)


def mcp_http_client(headers: dict[str, str] | None = None, timeout=None, auth=None):
    """httpx2 client (the HTTP stack of the MCP SDK) whose connections go through the same resolution check. Same defaults as the
    SDK's own factory; redirects are followed because every hop is validated when its connection is opened."""
    import httpx2
    from httpcore2._backends.anyio import AnyIOBackend

    class _SafeAsyncBackend(AnyIOBackend):
        async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            address = await asyncio.to_thread(_resolve_outbound_ip, host, port)
            return await super().connect_tcp(address, port, timeout=timeout, local_address=local_address, socket_options=socket_options)

    class _SafeAsyncTransport(httpx2.AsyncHTTPTransport):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self._pool._network_backend = _SafeAsyncBackend()

    kwargs: dict = {"transport": _SafeAsyncTransport(), "follow_redirects": True, "max_redirects": 5}
    kwargs["timeout"] = timeout if timeout is not None else httpx2.Timeout(30.0, read=300.0)
    if headers is not None:
        kwargs["headers"] = headers
    if auth is not None:
        kwargs["auth"] = auth
    return httpx2.AsyncClient(**kwargs)


def describe_outbound_error(exc: BaseException) -> str:
    """Short, fixed description of a failed outbound request, safe to store and show to a tenant (no addresses, no remote text)."""
    seen: set[int] = set()
    pending: list[BaseException] = [exc]
    names: list[str] = []
    while pending:
        current = pending.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, OutboundURLError):
            return "destination not allowed (not a public address)"
        names.extend(cls.__name__ for cls in type(current).__mro__)
        pending.extend(getattr(current, "exceptions", None) or ())
        if current.__cause__ is not None:
            pending.append(current.__cause__)
    if "TimeoutException" in names or "TimeoutError" in names:
        return "request timed out"
    if "ConnectError" in names or "ConnectionError" in names or "OSError" in names:
        return "connection failed"
    if "HTTPStatusError" in names:
        return "remote server answered with an error status"
    return "request failed"
