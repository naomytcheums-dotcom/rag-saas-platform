"""Connection-pool sizing shared by the API engine and the Celery task engines (PROD-003).

Behind a transaction-mode pooler (PgBouncer, Supabase port 6543) server connections are multiplexed, so a client-side pool of
5 + 10 per process is fine. Without one (direct or session-mode connection, which Supabase caps at 15 connections IN TOTAL) every
gunicorn worker (4 by default) and every Celery process holds its own pool: 4 x (5 + 10) = 60 potential connections is what produced the
`EMAXCONNSESSION` outage. The default is therefore 3 + 2 per process in that case. `SQLALCHEMY_POOL_SIZE`, `SQLALCHEMY_MAX_OVERFLOW`
and `SQLALCHEMY_POOL_TIMEOUT` still override either default."""

from collections.abc import Mapping

TRANSACTION_POOL_DEFAULTS = (5, 10)
DIRECT_POOL_DEFAULTS = (3, 2)
DEFAULT_POOL_TIMEOUT = 60


def resolve_pool_settings(environ: Mapping[str, str], transaction_mode: bool) -> tuple[int, int, int]:
    """(pool_size, max_overflow, pool_timeout) for one process."""
    default_size, default_overflow = TRANSACTION_POOL_DEFAULTS if transaction_mode else DIRECT_POOL_DEFAULTS
    return (
        int(environ.get("SQLALCHEMY_POOL_SIZE", default_size)),
        int(environ.get("SQLALCHEMY_MAX_OVERFLOW", default_overflow)),
        int(environ.get("SQLALCHEMY_POOL_TIMEOUT", DEFAULT_POOL_TIMEOUT)),
    )
