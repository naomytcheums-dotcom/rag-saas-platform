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
    HTTP layer) -- confirms a real log record becomes a real SystemLog row."""
    import logging

    from sqlalchemy import select

    from api.models.admin import SystemLog
    from api.security.system_log_handler import SystemLogHandler

    handler = SystemLogHandler()
    logger = logging.getLogger("test.system_log_handler")
    logger.addHandler(handler)
    logger.warning("a real warning captured by the real handler")
    logger.removeHandler(handler)

    # The handler uses its own sync engine against the real DATABASE_URL,
    # not the test's SQLite session -- verify against that real engine.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as SyncSession

    from api.config import settings

    sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""))
    with SyncSession(sync_engine) as sync_db:
        row = sync_db.execute(select(SystemLog).where(SystemLog.message == "a real warning captured by the real handler")).scalar_one_or_none()
        assert row is not None
        assert row.level == "WARNING"
        sync_db.delete(row)
        sync_db.commit()
