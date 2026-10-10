"""Specs 10.2.3 (data leakage), 10.2.5 (PII masking), 10.2.6 (sensitive information), 10.2.8 (unsafe tool calls) and 10.2.10 (output validation).

Dependency-free pattern checks, applied to text that is about to leave the platform (a model answer) or to arguments a model wants to pass to a tool.
They catch the common, well-formed cases (credentials, card numbers, e-mail addresses, phone numbers, IBANs, private-network URLs, destructive SQL); they
are NOT a data-loss-prevention product and will miss obfuscated or novel leaks. Findings carry only a type and a count, never the matched text."""

import ipaddress
import re
from urllib.parse import urlparse

# --- secrets (always sensitive) -------------------------------------------------------------------------------------------------------------
_SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY(?: BLOCK)?-----"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "api_key": re.compile(r"\b(?:sk|pk|rk)[-_](?:live|test|ant|proj)?[-_]?[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    "slack_token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "database_url": re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb|redis)(?:\+\w+)?://[^\s:@/]+:[^\s@/]+@[^\s/]+", re.I),
}

# --- personal data (masked when PII masking is on) ------------------------------------------------------------------------------------------
_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b"),
    "phone": re.compile(r"(?<!\w)(?:\+\d{1,3}[ .-]?)?(?:\(?\d{2,4}\)?[ .-]?){2,4}\d{2,4}(?!\w)"),
}
_CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")

_MASKS = {"email": "[EMAIL]", "iban": "[IBAN]", "phone": "[PHONE]", "card_number": "[CARD]"}


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _card_matches(text: str) -> list[re.Match[str]]:
    found = []
    for m in _CARD.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            found.append(m)
    return found


def scan_output(text: str, *, include_pii: bool = True) -> list[dict]:
    """Return `[{"type": ..., "count": n}]` for every kind of sensitive data present. Secrets are always reported; PII only when `include_pii`."""
    findings: list[dict] = []
    for kind, pattern in _SECRET_PATTERNS.items():
        count = len(pattern.findall(text))
        if count:
            findings.append({"type": kind, "count": count})
    if include_pii:
        for kind, pattern in _PII_PATTERNS.items():
            count = len(pattern.findall(text))
            if kind == "phone":  # long digit runs that are cards or IBANs are not phone numbers
                count = len([m for m in pattern.finditer(text) if 8 <= len(re.sub(r"\D", "", m.group())) <= 15 and not _luhn_ok(re.sub(r"\D", "", m.group()))])
            if count:
                findings.append({"type": kind, "count": count})
        cards = _card_matches(text)
        if cards:
            findings.append({"type": "card_number", "count": len(cards)})
    return findings


def redact_output(text: str, *, mask_pii: bool = True) -> tuple[str, list[dict]]:
    """Replace credentials with `[REDACTED:<type>]` and (optionally) personal data with `[EMAIL]`, `[CARD]`, ... Returns the new text and the findings."""
    findings = scan_output(text, include_pii=mask_pii)
    for kind, pattern in _SECRET_PATTERNS.items():
        text = pattern.sub(f"[REDACTED:{kind}]", text)
    if mask_pii:
        for m in reversed(_card_matches(text)):
            text = text[: m.start()] + _MASKS["card_number"] + text[m.end():]
        for kind in ("email", "iban"):
            text = _PII_PATTERNS[kind].sub(_MASKS[kind], text)
        text = _PII_PATTERNS["phone"].sub(lambda m: _MASKS["phone"] if 8 <= len(re.sub(r"\D", "", m.group())) <= 15 else m.group(), text)
    return text, findings


def validate_output(text: str | None, max_chars: int = 50_000) -> list[str]:
    """Structural problems of a model answer: empty, absurdly long, or containing control characters that could break a client."""
    problems = []
    if text is None or not text.strip():
        problems.append("empty")
        return problems
    if len(text) > max_chars:
        problems.append("too_long")
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text):
        problems.append("control_characters")
    return problems


# --- unsafe tool calls ----------------------------------------------------------------------------------------------------------------------
_DESTRUCTIVE_SQL = re.compile(r"\b(?:drop|alter|truncate|grant|revoke|create\s+role|create\s+user|copy\s+.+\s+program|pg_read_file|lo_import|lo_export)\b", re.I)
_METADATA_HOSTS = {"metadata.google.internal", "169.254.169.254", "metadata", "instance-data"}


def _url_is_internal(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https", "ftp") or not host:
        return False
    if host in _METADATA_HOSTS or host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified


def detect_unsafe_tool_call(tool_name: str, arguments: dict) -> list[str]:
    """Reasons for which a tool call requested by a model should not run: a URL pointing at the internal network or a cloud metadata service,
    a credential passed as an argument (exfiltration), or DDL / privilege statements in a SQL-like argument. Empty list = nothing suspicious."""
    reasons: list[str] = []
    values = [v for v in arguments.values() if isinstance(v, str)] if isinstance(arguments, dict) else []
    for value in values:
        if _url_is_internal(value.strip()):
            reasons.append("internal_url")
        if any(p.search(value) for p in _SECRET_PATTERNS.values()):
            reasons.append("credential_in_arguments")
        if "sql" in tool_name.lower() and _DESTRUCTIVE_SQL.search(value):
            reasons.append("destructive_sql")
    return sorted(set(reasons))
