"""Local preview API on a throw-away SQLite file. It never touches production data, and refuses to start if anything points outside this machine.

    python scripts/dev_isolated_server.py            # serves on http://127.0.0.1:8765, database in <temp>/rag-preview.db

The project's .env points at the real Supabase / Redis / S3 / payment providers. This wrapper replaces the database with a local SQLite file and blanks every
other external service BEFORE the application is imported, then checks the result (`assert_local_environment`) so a mistake fails loudly instead of writing
test accounts into production (which happened once on 2026-10-10).
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")
# Variables that must be empty or local once the wrapper has run.
EXTERNAL_VARS = (
    "DATABASE_URL", "DATABASE_URL_TRANSACTION", "REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "RATE_LIMIT_REDIS_URL",
    "CACHE_REDIS_URL", "S3_ENDPOINT_URL", "RESEND_API_KEY", "STRIPE_SECRET_KEY", "PAYSTACK_SECRET_KEY", "SENTRY_DSN",
)
# Variables blanked outright (the preview needs none of them).
BLANKED_VARS = tuple(v for v in EXTERNAL_VARS if v not in ("DATABASE_URL",)) + ("S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")


def assert_local_environment(env: dict[str, str]) -> None:
    """Raise SystemExit if any external-service variable is set to something that is neither empty, a SQLite URL nor a local host."""
    for name in EXTERNAL_VARS:
        value = env.get(name, "")
        if value and not value.startswith("sqlite") and not any(host in value for host in LOCAL_HOSTS):
            raise SystemExit(f"REFUSED: {name} is not local/empty - the preview must never touch production.")


def configure_environment(db_path: str, env: dict[str, str] | None = None) -> dict[str, str]:
    """Point the database at `db_path` (SQLite) and blank every other external service. Returns the environment it prepared."""
    target = os.environ if env is None else env
    target["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(db_path).as_posix()}"
    for name in BLANKED_VARS:
        target[name] = ""
    target["RATE_LIMIT_ENABLED"] = "false"
    target["APP_CACHE_ENABLED"] = "false"
    target["FRONTEND_URL"] = "http://localhost:3001"
    target.setdefault("JWT_SECRET_KEY", "local-preview-only-secret-0123456789abcdef")
    target.setdefault("COOKIE_SECURE", "false")
    assert_local_environment(target)
    return target


def main() -> None:
    db_path = os.environ.get("PREVIEW_DB_PATH") or str(Path(tempfile.gettempdir()) / "rag-preview.db")
    configure_environment(db_path)
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))

    from sqlalchemy import select  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: PLC0415

    import api.main as main_module  # noqa: PLC0415
    import api.security.rbac as rbac  # noqa: PLC0415
    from api.database import Base  # noqa: PLC0415
    from api.models.admin import Plan  # noqa: PLC0415

    engine = create_async_engine(os.environ["DATABASE_URL"])
    real_init = rbac.init_rbac

    async def init_rbac(bind_engine=None):
        from casbin_async_sqlalchemy_adapter import Base as CasbinBase  # noqa: PLC0415

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(CasbinBase.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            if not (await session.execute(select(Plan))).first():
                for key, name, monthly, yearly in (("free", "Free", 0, 0), ("starter", "Starter", 4900, 49000), ("pro", "Pro", 19900, 199000), ("enterprise", "Enterprise", 99900, 999000)):
                    session.add(Plan(key=key, name=name, monthly_price_cents=monthly, yearly_price_cents=yearly))
                await session.commit()
        return await real_init(engine)

    main_module.init_rbac = init_rbac

    import uvicorn  # noqa: PLC0415

    uvicorn.run(main_module.app, host="127.0.0.1", port=int(os.environ.get("PREVIEW_PORT", "8765")))


if __name__ == "__main__":
    main()
