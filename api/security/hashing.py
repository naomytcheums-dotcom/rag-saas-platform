"""
Two different hashing strategies for two different kinds of secret:

- Passwords are low-entropy and human-chosen -- bcrypt is deliberately
  slow so a stolen hash resists offline brute-forcing. Calls the `bcrypt`
  package directly rather than through passlib: passlib is unmaintained
  (last release 2020) and its own internal backend self-test crashes
  against current bcrypt releases (bcrypt>=4.1 raises instead of silently
  truncating on a >72-byte secret, which is exactly what passlib's
  self-test feeds it) -- a real, currently-reproducing incompatibility,
  not a hypothetical one to guard against.
- Refresh tokens, password-reset tokens and email OTP codes are either
  high-entropy random values (secrets.token_urlsafe) or, for the 6-digit
  OTP, short-lived and rate-limited -- bcrypt's slowness buys nothing there
  and would make every /auth/refresh call unnecessarily expensive. A plain
  SHA-256 digest is the standard choice for this case: fast, and a stolen
  DB dump still can't be reversed back to the original token.
"""

import hashlib
import secrets

import bcrypt

_BCRYPT_ROUNDS = 12  # ~250ms/hash on typical hardware; the current OWASP-recommended floor


def hash_password(password: str) -> str:
    """One-way bcrypt hash for storing a user's password. The salt is
    generated fresh each call (bcrypt.gensalt()) and embedded in the
    returned hash itself, so verify_password below needs no separate
    salt column to look up."""
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("ascii")


def verify_password(password: str, hashed_password: str) -> bool:
    """Checks a login attempt's plaintext password against the stored
    hash. bcrypt.checkpw does this in constant time, so the check itself
    can't leak how much of the password matched via timing."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("ascii"))


def hash_token(raw_token: str) -> str:
    """One-way SHA-256 hash for refresh tokens, password-reset tokens,
    and email OTP codes -- see this module's top docstring for why these
    use a fast hash instead of bcrypt. Deterministic (same input always
    produces the same hash), unlike hash_password's salted bcrypt, which
    is exactly what lets a lookup like `WHERE token_hash = :hash` work at
    all here."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_raw_token() -> str:
    """High-entropy opaque token for refresh tokens / password-reset links."""
    return secrets.token_urlsafe(48)


def generate_otp_code() -> str:
    """A 6-digit numeric code, zero-padded -- secrets.randbelow is a CSPRNG,
    unlike `random`, which must never be used for anything security-sensitive."""
    return f"{secrets.randbelow(1_000_000):06d}"
