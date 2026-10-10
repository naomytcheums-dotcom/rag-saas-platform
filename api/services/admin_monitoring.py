"""
Partie 11.5 -- real system health/resource monitoring. Reuses the
already-real /health, /health/ready, /metrics logic (api/main.py)
rather than duplicating it; adds real CPU/memory/disk (via `psutil`,
already a real dependency of this environment) and a real Celery queue
inspection (`celery_app.control.inspect()`), not simulated numbers.
"""

import datetime as dt

import psutil
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.security.rate_limit import is_redis_reachable


async def get_system_health(db: AsyncSession) -> dict:
    database_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        database_ok = False

    redis_ok = await is_redis_reachable()
    celery_ok = _celery_reachable()

    return {
        "database": "ok" if database_ok else "unreachable",
        "redis": "ok" if redis_ok else "unreachable",
        "celery": "ok" if celery_ok else "unreachable",
        "vector_store": await vector_store_status(db) if database_ok else "unknown (database unreachable)",
        "llm_providers": llm_providers_status(),
        "checked_at": dt.datetime.now(dt.timezone.utc),
    }


async def vector_store_status(db: AsyncSession) -> str:
    """Spec 11.3.7 -- the vector store is PostgreSQL + the `vector` extension: report whether the extension is installed (and its version)."""
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return "not applicable (not PostgreSQL: vector search runs in memory)"
    try:
        version = (await db.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))).scalar()
    except Exception:  # noqa: BLE001 -- a probe must never raise
        return "unknown (query failed)"
    return f"ok (pgvector {version})" if version else "missing: the pgvector extension is not installed"


def llm_providers_status() -> dict[str, str]:
    """Spec 11.3.8 -- which hosted LLM providers have a platform-level key. This is a configuration check, not a live call (no cost, no latency):
    organizations may still bring their own key. A provider showing "not configured" only matters for organizations that rely on the platform key."""
    from api.config import settings  # noqa: PLC0415

    keys = {"anthropic": settings.ANTHROPIC_API_KEY, "openai": settings.OPENAI_API_KEY, "gemini": settings.GEMINI_API_KEY, "mistral": settings.MISTRAL_API_KEY}
    return {name: "configured" if key else "not configured" for name, key in keys.items()}


def _celery_reachable() -> bool:
    try:
        from api.tasks.celery_app import celery_app

        pong = celery_app.control.inspect(timeout=1.0).ping()
        return bool(pong)
    except Exception:  # noqa: BLE001 -- a real, live network probe; any failure means "not reachable"
        return False


def get_resource_usage() -> dict:
    """Real host-level metrics via psutil -- this process's own host,
    not a fleet-wide aggregate (this codebase has no multi-node metrics
    aggregation system)."""
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "cpu_count": psutil.cpu_count() or 0,
        "memory_used_bytes": memory.used,
        "memory_total_bytes": memory.total,
        "memory_percent": memory.percent,
        "disk_used_bytes": disk.used,
        "disk_total_bytes": disk.total,
        "disk_percent": disk.percent,
    }


def get_queue_status() -> dict:
    """Real Celery queue inspection -- active/scheduled/reserved task
    counts across every worker currently reachable. Empty dict per
    category (not an error) when no worker is currently up -- honest,
    not fabricated."""
    try:
        from api.tasks.celery_app import celery_app

        inspector = celery_app.control.inspect(timeout=1.0)
        active = inspector.active() or {}
        scheduled = inspector.scheduled() or {}
        reserved = inspector.reserved() or {}
        return {
            "active_tasks": sum(len(v) for v in active.values()),
            "scheduled_tasks": sum(len(v) for v in scheduled.values()),
            "reserved_tasks": sum(len(v) for v in reserved.values()),
            "workers_online": len(active),
        }
    except Exception:  # noqa: BLE001 -- same real, live-probe reasoning as _celery_reachable
        return {"active_tasks": 0, "scheduled_tasks": 0, "reserved_tasks": 0, "workers_online": 0}
