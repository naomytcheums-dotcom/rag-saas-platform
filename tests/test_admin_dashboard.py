"""Partie 11.1/11.5/11.6 -- global stats, monitoring, system logs."""


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _make_admin(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.admin
    await db_session.commit()
    return token, user


async def test_global_stats_endpoint_real_counts(client, db_session, register_payload):
    token, _ = await _make_admin(client, db_session, register_payload)
    response = await client.get("/admin/stats", headers=_auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body["users"]["total"] >= 1
    assert body["revenue"]["mrr_cents"] == 0  # no real payment processor -- honestly 0, not fabricated


async def test_stats_endpoints_require_admin(client, db_session, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.get("/admin/stats", headers=_auth_header(token))
    assert response.status_code == 404  # require_admin's anti-enumeration


async def test_monitoring_health_endpoint(client, db_session, register_payload):
    token, _ = await _make_admin(client, db_session, register_payload)
    response = await client.get("/admin/monitoring/health", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["database"] == "ok"  # a real SELECT 1 against the real test DB


async def test_monitoring_resources_endpoint_real_psutil(client, db_session, register_payload):
    token, _ = await _make_admin(client, db_session, register_payload)
    response = await client.get("/admin/monitoring/resources", headers=_auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body["cpu_count"] >= 1
    assert body["memory_total_bytes"] > 0


async def test_system_logs_list_and_stats(client, db_session, register_payload):
    from api.models.admin import SystemLog

    token, _ = await _make_admin(client, db_session, register_payload)

    db_session.add(SystemLog(level="ERROR", logger_name="api.test", message="a real test error"))
    await db_session.commit()

    listing = await client.get("/admin/logs", headers=_auth_header(token))
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["message"] == "a real test error"

    stats = await client.get("/admin/logs/stats", headers=_auth_header(token))
    assert stats.status_code == 200
    assert stats.json()["by_level"]["ERROR"] == 1


async def test_purge_logs_requires_superadmin(client, db_session, register_payload):
    token, _ = await _make_admin(client, db_session, register_payload)  # admin, not superadmin
    response = await client.delete("/admin/logs/purge?older_than_days=1", headers=_auth_header(token))
    assert response.status_code == 403


async def test_system_log_handler_writes_real_rows(db_session):
    """Real, direct test of the logging.Handler itself (not via the
    HTTP layer) -- confirms a real log record becomes a real SystemLog row.

    Real bug fixed here (CI-orphan audit, 2026-09-16), in two layers:

    1. This test writes to the REAL, SHARED DATABASE_URL (the handler's
       own sync engine, not the test's isolated SQLite session -- see
       below), using the exact same fixed message every run. This test
       had never run in CI before (see docs/audit/COHERENCE.md), so a
       first real, failed run somewhere left a duplicate row behind
       uncleaned -- `scalar_one_or_none()` threw `MultipleResultsFound`
       before ever reaching the cleanup at the bottom, so every
       subsequent run failed the SAME way without being able to
       self-heal (the failure itself blocked the only cleanup path).
       Fixed with a UUID-suffixed message plus cleaning up ALL matching
       rows on teardown, not `scalar_one_or_none`'s single-row
       assumption.

    2. Even with a unique message per run, this test STILL failed
       intermittently when run as part of the full combined suite (never
       standalone): `install_system_log_handler()`
       (api/security/system_log_handler.py) attaches its OWN
       `SystemLogHandler` to the ROOT logger the first time any test's
       FastAPI app fixture actually runs a real lifespan startup --
       idempotent, so once any earlier test in the same pytest process
       triggers it, it stays installed for every test after. This
       test's own logger ("test.system_log_handler") propagates to that
       ancestor handler by default, so `logger.warning(message)` was
       silently writing the row TWICE -- once via this test's own
       explicit handler, once via the globally-installed one -- whenever
       that root handler happened to already be installed by test
       order. Fixed by disabling propagation on this specific,
       test-only logger, so it only ever reaches the one handler this
       test explicitly attached, regardless of what else has run
       before it in the same process."""
    import logging
    import uuid

    from sqlalchemy import select

    from api.models.admin import SystemLog
    from api.security.system_log_handler import SystemLogHandler

    message = f"a real warning captured by the real handler ({uuid.uuid4()})"
    handler = SystemLogHandler()
    logger = logging.getLogger("test.system_log_handler")
    logger.propagate = False
    logger.addHandler(handler)
    logger.warning(message)
    logger.removeHandler(handler)

    # The handler uses its own sync engine against the real DATABASE_URL,
    # not the test's SQLite session -- verify against that real engine.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as SyncSession

    from api.config import settings

    sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""))
    with SyncSession(sync_engine) as sync_db:
        rows = sync_db.scalars(select(SystemLog).where(SystemLog.message == message)).all()
        assert len(rows) == 1
        assert rows[0].level == "WARNING"
        for row in rows:
            sync_db.delete(row)
        sync_db.commit()
