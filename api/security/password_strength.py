"""
1.1-audit finding: password.min_length=8 was the only strength check
anywhere in this app -- no complexity rule, no common-password blocklist,
no check against known-breached passwords. Complexity rules (require an
uppercase/digit/symbol) are widely considered obsolete by current NIST
guidance (SP 800-63B) and mostly just push users toward predictable
substitutions ("Password1!"); checking against passwords already known to
be compromised is the actually-effective replacement NIST recommends
instead, and what this module does.

Uses the Have I Been Pwned Pwned Passwords API's k-anonymity mode: only
the first 5 hex characters of the password's SHA-1 hash are ever sent
over the network, never the password itself or its full hash -- HIBP
returns every suffix sharing that prefix and the match is found locally.
This is the same privacy model 1Password, Firefox, and many other real
products use against this exact API.

Fails OPEN (treats an unreachable API as "not known to be pwned") on any
network error, same reasoning as every other optional external
dependency in this codebase (Resend, S3, rate-limit Redis, see their
docstrings) -- a third-party API being down must not block registration,
password reset, or any other flow that needs this check.
"""

import hashlib
import logging

import httpx

logger = logging.getLogger(__name__)

_HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/"
_HIBP_TIMEOUT_SECONDS = 3.0


async def is_password_known_breached(password: str) -> bool:
    """True only if HIBP's dataset confirms this exact password has
    appeared in a known breach. False for "not found" AND for "couldn't
    check" (network error/timeout/non-200) -- callers must not treat
    those two as distinguishable, see this module's docstring on the
    fail-open design."""
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]

    try:
        async with httpx.AsyncClient(timeout=_HIBP_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{_HIBP_RANGE_URL}{prefix}", headers={"Add-Padding": "true"})
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("HaveIBeenPwned check failed, allowing the password through: %s", exc)
        return False

    for line in response.text.splitlines():
        candidate_suffix, _count = line.strip().split(":")
        if candidate_suffix == suffix:
            return True
    return False
