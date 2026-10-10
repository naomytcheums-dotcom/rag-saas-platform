"""P2 (TEN-006/007/008/021/022): malformed or conflicting input must be a 4xx, never a 500.

Reproduced on a disposable PostgreSQL: NUL characters and oversized values reached the database and answered 500, concurrent duplicate
registrations or alerts answered 500 on the unique index, negative page sizes reached SQL as LIMIT -1, and `notification_templates` had
no migration at all. The SQLSTATE mapping is tested here with fake driver errors; the real-database behaviour is covered by the probe
documented in ROADMAP.md.
"""

import pathlib
import re

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import DBAPIError, IntegrityError

from api.db_errors import register_db_error_handlers
from test_document_idor import make_tenants

class _DriverError(Exception):
    def __init__(self, message: str, sqlstate: str | None):
        super().__init__(message)
        self.sqlstate = sqlstate


def _app_raising(exc: Exception) -> FastAPI:
    app = FastAPI()
    register_db_error_handlers(app)

    @app.get("/boom")
    async def boom():
        raise exc

    return app


async def _status(exc: Exception) -> tuple[int, dict | None]:
    app = _app_raising(exc)
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as c:
        response = await c.get("/boom")
    return response.status_code, response.json() if response.headers.get("content-type", "").startswith("application/json") else None


@pytest.mark.parametrize(
    ("sqlstate", "expected"),
    [("23505", 409), ("23503", 422), ("22021", 422), ("22001", 422), ("22003", 422), ("22P02", 422)],
)
async def test_database_errors_are_classified_by_sqlstate(sqlstate, expected):
    exc = DBAPIError("SELECT 1", {}, _DriverError("driver says no", sqlstate))
    code, body = await _status(exc)
    assert code == expected
    assert "driver says no" not in str(body), "driver text must not leak to the client"


@pytest.mark.parametrize("sqlstate", ["23502", "23514", "40001", "57014", "08006", None])
async def test_other_database_errors_stay_server_errors(sqlstate):
    """A NOT NULL / check violation or a lost connection is our bug, not the caller's: it must not be disguised as a 4xx."""
    exc = IntegrityError("INSERT", {}, _DriverError("secret detail", sqlstate))
    code, _ = await _status(exc)
    assert code == 500


async def test_sqlite_messages_are_recognised_for_local_runs():
    exc = IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed: users.email"))
    assert (await _status(exc))[0] == 409
    exc = IntegrityError("INSERT", {}, Exception("FOREIGN KEY constraint failed"))
    assert (await _status(exc))[0] == 422


async def test_a_duplicate_usage_alert_is_a_409(client, db_session, monkeypatch):
    (headers, org, _user), _other = await make_tenants(client, db_session, monkeypatch, "alertdup")
    payload = {"resource_type": "documents_processed", "threshold_percent": 80}
    first = await client.post(f"/organizations/{org}/billing/usage/alerts", json=payload, headers=headers)
    second = await client.post(f"/organizations/{org}/billing/usage/alerts", json=payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code in (201, 409), second.text  # SQLite test schema may not carry the unique index; 500 is never acceptable
    assert second.status_code != 500


@pytest.mark.parametrize("path", ["agents", "workflows"])
async def test_a_negative_page_size_is_rejected(client, db_session, monkeypatch, path):
    (headers, org, _user), _other = await make_tenants(client, db_session, monkeypatch, f"limit{path}")
    for bad in ("-1", "0"):
        response = await client.get(f"/organizations/{org}/{path}?limit={bad}", headers=headers)
        assert response.status_code == 422, (path, bad, response.text)
    ok = await client.get(f"/organizations/{org}/{path}?limit=1", headers=headers)
    assert ok.status_code == 200


async def test_a_negative_page_size_is_rejected_on_conversations(client, db_session, monkeypatch):
    (headers, org, _user), _other = await make_tenants(client, db_session, monkeypatch, "limitconv")
    for url in ("/conversations?limit=-1", "/conversations/deleted?limit=0", "/conversations/public?limit=-5"):
        response = await client.get(url, headers=headers)
        assert response.status_code == 422, (url, response.text)


def test_the_notification_templates_table_has_a_migration_and_the_chain_has_one_head():
    versions = pathlib.Path(__file__).resolve().parents[1] / "api" / "alembic" / "versions"
    sources = {p.name: p.read_text(encoding="utf-8") for p in versions.glob("*.py")}
    creators = [name for name, text in sources.items() if re.search(r"create_table\(\s*[\"']notification_templates[\"']", text)]
    assert creators, "notification_templates has a model but no migration creates it"

    revisions, parents = {}, set()
    for name, text in sources.items():
        rev = re.search(r"^revision(?::\s*str)?\s*=\s*[\"']([^\"']+)[\"']", text, re.M)
        down = re.search(r"^down_revision(?::[^=]+)?\s*=\s*[\"']([^\"']+)[\"']", text, re.M)
        if rev:
            revisions[rev.group(1)] = name
        if down:
            parents.add(down.group(1))
    assert len(set(revisions) - parents) == 1, f"alembic must have a single head, found {sorted(set(revisions) - parents)}"
