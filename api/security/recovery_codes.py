"""
1.1.7 2FA recovery codes -- issued once when 2FA is enabled, so a user who
loses their authenticator device (phone lost, reset, or the app
uninstalled) isn't permanently locked out of an account that otherwise
requires a TOTP code to log in.

Ten single-use codes are generated per batch (the same count GitHub,
Google, and AWS all issue). Each is shown to the user exactly once, at
generation time, in plaintext -- like a password, the raw value is never
stored, only its SHA-256 hash (api/security/hashing.py's hash_token), so a
stolen database dump can't be used to log in even if every row is read.
"""

import secrets

RECOVERY_CODE_COUNT = 10

# Crockford-ish alphabet: excludes 0/O and 1/I/L, the characters people
# most often transcribe wrong when copying a code off a screen by hand.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_recovery_code() -> str:
    """One human-typeable code, e.g. "7K9P-QX3M-2VYT". The dashes are
    purely for readability -- normalize_recovery_code strips them before
    hashing/comparison, so they carry no entropy of their own."""
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(12))
    return f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"


def normalize_recovery_code(code: str) -> str:
    """Strips whitespace/dashes and uppercases before hashing, so
    "7k9p qx3m 2vyt" and "7K9P-QX3M-2VYT" hash identically -- users will
    type these back in inconsistently, unlike a copy-pasted token."""
    return "".join(code.split()).replace("-", "").upper()
