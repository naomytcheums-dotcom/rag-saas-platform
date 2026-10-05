"""P2C-1: real SQLite document ownership, with no storage or worker calls."""

import uuid
from unittest.mock import AsyncMock, Mock

from sqlalchemy import inspect, select
from starlette.routing import Match

from api.main import app
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.user import User


async def make_tenants(client, db_session, monkeypatch, label):
    """Shared local setup for the nine dedicated corrective tests."""
    monkeypatch.setattr("api.routers.auth.create_and_send_email_otp", AsyncMock())
    tenants = []
    for suffix in ("a", "b"):
        email = f"p2c-{label}-{suffix}@example.com"
        registered = await client.post(
            "/auth/register",
            json={
                "email": email,
                "password": "correct-horse-battery-staple",
                "accept_terms": True,
            },
        )
        assert registered.status_code == 201, "Local user registration failed"
        headers = {"Authorization": "Bearer " + registered.json()["access_token"]}
        created = await client.post(
            "/organizations", headers=headers, json={"name": f"P2C {label} {suffix}"}
        )
        assert created.status_code == 201, created.text
        user = await db_session.scalar(select(User).where(User.email == email))
        assert user is not None
        tenants.append((headers, uuid.UUID(created.json()["id"]), user.id))
    assert tenants[0][1:] != tenants[1][1:]
    assert db_session.bind.dialect.name == "sqlite"
    return tenants


async def snapshot(db_session, *rows):
    result = []
    for row in rows:
        table = row.__table__
        identity = inspect(row).identity
        assert identity is not None, "Snapshot requires a persisted real row"
        stored = (
            await db_session.execute(select(table).where(table.c.id == identity[0]))
        ).mappings().one()
        result.append(dict(stored))
    return result


async def make_key(client, headers, org_id, scopes):
    created = await client.post(
        f"/organizations/{org_id}/api-keys",
        headers=headers,
        json={"name": "p2c-local-key", "scopes": scopes},
    )
    assert created.status_code == 200, "Local API key creation failed"
    return {"X-API-Key": created.json()["key"]}


async def denied(client, method, path, headers, violations, expected=(403, 404), **kwargs):
    # A routing 404 must never masquerade as a successful authorization test.
    scope = {"type": "http", "path": path.split("?")[0], "method": method, "root_path": ""}
    assert any(route.matches(scope)[0] == Match.FULL for route in app.routes), (
        f"ROUTE_MISMATCH: {method} {path}"
    )
    response = await client.request(method, path, headers=headers, **kwargs)
    print(f"{method} {path} -> {response.status_code}")
    if response.status_code not in expected:
        violations.append(f"{method} {path}: expected {expected}, got {response.status_code}")
    return response


async def test_document_idor(client, db_session, monkeypatch):
    (owner, org_a, _), (attacker, _, _) = await make_tenants(
        client, db_session, monkeypatch, "document"
    )
    document = Document(
        organization_id=org_a,
        name="private-document.txt",
        file_key="p2c/private-document.txt",
        file_size=19,
        file_type="text/plain",
        status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    chunk = DocumentChunk(
        document_id=document.id,
        organization_id=org_a,
        content="private-document-content",
        chunk_index=0,
        embedding=[0.0, 1.0],
        metadata_json={},
    )
    db_session.add(chunk)
    await db_session.commit()
    baseline = await snapshot(db_session, document, chunk)
    storage = AsyncMock()
    schedule = Mock()
    monkeypatch.setattr("api.routers.documents.stream_document_file", storage)
    monkeypatch.setattr("api.security.documents.schedule_document_reindex", schedule)
    control = await client.get(f"/documents/{document.id}", headers=owner)
    assert control.status_code == 200, control.text
    violations = []
    for suffix in ("", "/metadata", "/preview", "/status", "/versions", "/progress/stream"):
        await denied(client, "GET", f"/documents/{document.id}{suffix}", attacker, violations)
    await denied(client, "GET", f"/organizations/{org_a}/documents", attacker, violations)
    await denied(client, "POST", f"/documents/{document.id}/reindex", attacker, violations)
    await denied(client, "DELETE", f"/documents/{document.id}", attacker, violations)
    assert await snapshot(db_session, document, chunk) == baseline
    storage.assert_not_called()
    schedule.assert_not_called()
    assert not violations, "\n".join(violations)
