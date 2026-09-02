"""
Audit finding 30: an allowlist of IPs/CIDR ranges (TRUSTED_IPS) exempted
from rate limiting entirely by api/security/adaptive_rate_limit.py -- for
known-safe traffic sources (internal tooling, a company VPN egress IP, a
monitoring/synthetic-check service) that would otherwise share the same
brute-force limits as an anonymous public caller.

Security-critical distinction: is_trusted_ip() below is deliberately
checked against direct_peer_ip() (the real TCP connection's peer
address), NEVER api/utils.py's client_ip() -- that helper prefers the
client-supplied X-Forwarded-For header, which its own docstring already
flags as trustworthy only behind a real reverse proxy that sets/
overwrites it itself. Using client_ip() here would turn TRUSTED_IPS into
a complete self-service rate-limit bypass: any anonymous caller could set
`X-Forwarded-For: <a trusted IP>` and skip brute-force protection on
login/register entirely. The geo-adaptive multiplier
(api/security/geoip.py) can safely keep using client_ip(), because it
only ever ADJUSTS a limit up or down -- the same trust level every other
per-IP rate-limit key in this codebase already operates at. An outright
bypass is a strictly bigger risk and gets a strictly stricter check.
"""

import ipaddress
from functools import lru_cache

from fastapi import Request

from api.config import settings


@lru_cache(maxsize=8)
def _parse_trusted_networks(raw: str) -> tuple:
    """Cached by the raw settings string itself (not the empty-args
    pattern), so a test that monkeypatches settings.TRUSTED_IPS to a new
    value gets a fresh parse rather than a stale one -- lru_cache keys on
    the argument, and a changed string is simply a new cache entry."""
    networks = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            continue
    return tuple(networks)


def is_trusted_ip(ip: str | None) -> bool:
    """True if `ip` exactly matches, or falls within a CIDR range listed
    in, settings.TRUSTED_IPS. False for anything unparseable or absent --
    never raises, so a bad manual edit to TRUSTED_IPS degrades to "no
    exemptions" rather than crashing every request."""
    if not ip:
        return False
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(address in network for network in _parse_trusted_networks(settings.TRUSTED_IPS))


def direct_peer_ip(request: Request) -> str | None:
    """The actual TCP connection's peer address -- deliberately bypasses
    api/utils.py's client_ip() and its X-Forwarded-For preference, see
    this module's top docstring for why that distinction is load-bearing
    here specifically."""
    return request.client.host if request.client else None
