"""Driver-safe PostgreSQL URLs for synchronous database consumers."""

from sqlalchemy.engine import URL, make_url

_SSL_MODES = frozenset({"disable", "allow", "prefer", "require", "verify-ca", "verify-full"})


def synchronous_database_url(value: str | URL) -> URL:
    """Convert asyncpg's SSL option to libpq without weakening its mode.

    Return a URL object so decoded credentials and repeated query parameters
    never pass through string replacement or password-masking serialization.
    Conflicting or ambiguous SSL options fail closed rather than choosing one.
    """
    url = make_url(value)
    if url.drivername not in {"postgresql", "postgresql+asyncpg", "postgresql+psycopg2"}:
        raise ValueError("A PostgreSQL URL is required for the synchronous database engine.")

    query = dict(url.query)
    for key in ("ssl", "sslmode"):
        if key in query and query[key] not in _SSL_MODES:
            raise ValueError(f"{key} must specify exactly one supported PostgreSQL SSL mode.")
    if "ssl" in query:
        ssl = query.pop("ssl")
        if "sslmode" in query and query["sslmode"] != ssl:
            raise ValueError("Conflicting PostgreSQL ssl and sslmode options.")
        query["sslmode"] = ssl
    return url.set(drivername="postgresql+psycopg2", query=query)
