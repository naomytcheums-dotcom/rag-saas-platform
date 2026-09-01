"""Small cross-cutting helpers with no single obvious home."""

import datetime as dt


def utcnow() -> dt.datetime:
    """The one way this app ever gets the current time -- always
    timezone-aware UTC, never a naive datetime.now(). A single shared
    helper means every "now" in the codebase is directly comparable to
    every timestamp read back from the database."""
    return dt.datetime.now(dt.timezone.utc)


def as_aware_utc(value: dt.datetime) -> dt.datetime:
    """Postgres round-trips a DateTime(timezone=True) column back as
    tz-aware; SQLite (used in tests, see tests/conftest.py) does not -- a
    value written aware comes back naive. Every datetime this app ever
    writes is already UTC (utcnow() above), so treating a naive value as
    UTC on read is a correct normalization, not a guess."""
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)
