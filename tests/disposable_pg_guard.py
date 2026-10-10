"""Guard for the tests that write to a real PostgreSQL (invoice concurrency): decides, from the environment only, whether a database may
be used. Pure functions, unit-tested in test_disposable_pg_guard.py. The goal is that a tunnel to a shared or real database can never
be mistaken for a throwaway one: a local host is not enough."""

import re
from urllib.parse import urlparse

_MARKER = re.compile(r"(disposable|roundtrip|scratch|throwaway)", re.IGNORECASE)
_LOCAL = {"127.0.0.1", "localhost"}


def _parts(url: str):
    parsed = urlparse(url.replace("+asyncpg", ""))
    host = (parsed.hostname or "").lower()
    host = "127.0.0.1" if host == "localhost" else host
    return host, parsed.port or 5432, parsed.path.lstrip("/")


def disposable_pg_refusal(url: str, confirm: str | None, *application_urls: str | None) -> str | None:
    """None when the database may be used, otherwise the reason it is refused (never contains credentials).

    Required: a local host; a database name containing disposable, roundtrip, scratch or throwaway; an explicit confirmation equal to
    that name; a target different (host, port, database) from every application database URL given."""
    if not url:
        return "RAG_DISPOSABLE_PG_URL is not set"
    host, port, database = _parts(url)
    if host not in _LOCAL:
        return "RAG_DISPOSABLE_PG_URL is not a local database (127.0.0.1 or localhost only)"
    if not database or not _MARKER.search(database):
        return "the database name must contain disposable, roundtrip, scratch or throwaway"
    if not confirm or confirm != database:
        return "RAG_DISPOSABLE_PG_CONFIRM must be set to the exact database name"
    for application_url in application_urls:
        if application_url and _parts(application_url) == (host, port, database):
            return "the target is the application's own DATABASE_URL"
    return None
