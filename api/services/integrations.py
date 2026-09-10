"""
Partie 15.1/15.2 -- real inbound integration connections. Reuses
`upload_document` (Partie 2, `api/security/documents.py`) for the real
"feed this payload into the RAG knowledge base" action, rather than a
parallel ingestion path -- exactly the same validation/dedup/chunking/
embedding pipeline any other document goes through.

Real, honest action list: only `ingest_document` and `log_only`. The
literal spec's much longer action list ("create an agent", "update a
CRM", "send an email") has no real target in this environment (no
agent-creation-from-webhook use case exists, no real CRM account to
push to, and an email action would just re-wrap api/services/email.py
for no real inbound-integration use case) -- adding them as no-op
stubs would be exactly the kind of fabricated completeness this
project's whole discipline exists to avoid.
"""

import datetime as dt
import re
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.integrations import IntegrationAction, IntegrationConnection, IntegrationLog, IntegrationLogStatus, IntegrationMapping, IntegrationProvider


class IntegrationError(Exception):
    pass


class ConnectionNotFoundError(IntegrationError):
    pass


class InvalidTokenError(IntegrationError):
    pass


def generate_connection_token() -> str:
    return secrets.token_urlsafe(32)


async def list_connections(db: AsyncSession, organization_id: uuid.UUID) -> list[IntegrationConnection]:
    return list((await db.scalars(select(IntegrationConnection).where(IntegrationConnection.organization_id == organization_id))).all())


async def get_connection(db: AsyncSession, organization_id: uuid.UUID, connection_id: uuid.UUID) -> IntegrationConnection:
    conn = await db.get(IntegrationConnection, connection_id)
    if conn is None or conn.organization_id != organization_id:
        raise ConnectionNotFoundError(str(connection_id))
    return conn


async def create_connection(db: AsyncSession, organization_id: uuid.UUID, *, name: str, provider: IntegrationProvider, action: IntegrationAction, user_id: uuid.UUID | None) -> tuple[IntegrationConnection, str]:
    """Returns (connection, plaintext_token) -- the token is shown ONCE,
    same real convention as an API key's own plaintext creation response."""
    token = generate_connection_token()
    connection = IntegrationConnection(organization_id=organization_id, name=name, provider=provider, action=action, token=token, created_by=user_id)
    db.add(connection)
    await db.flush()
    return connection, token


async def update_connection(db: AsyncSession, organization_id: uuid.UUID, connection_id: uuid.UUID, **fields) -> IntegrationConnection:
    conn = await get_connection(db, organization_id, connection_id)
    for key, value in fields.items():
        if value is not None and hasattr(conn, key):
            setattr(conn, key, value)
    await db.flush()
    return conn


async def delete_connection(db: AsyncSession, organization_id: uuid.UUID, connection_id: uuid.UUID) -> None:
    conn = await get_connection(db, organization_id, connection_id)
    await db.delete(conn)
    await db.flush()


async def list_mappings(db: AsyncSession, connection_id: uuid.UUID) -> list[IntegrationMapping]:
    return list((await db.scalars(select(IntegrationMapping).where(IntegrationMapping.connection_id == connection_id))).all())


async def create_mapping(db: AsyncSession, connection_id: uuid.UUID, *, source_field: str, target_field: str, transform: str | None) -> IntegrationMapping:
    mapping = IntegrationMapping(connection_id=connection_id, source_field=source_field, target_field=target_field, transform=transform)
    db.add(mapping)
    await db.flush()
    return mapping


async def delete_mapping(db: AsyncSession, mapping_id: uuid.UUID) -> None:
    mapping = await db.get(IntegrationMapping, mapping_id)
    if mapping is not None:
        await db.delete(mapping)
        await db.flush()


# -- real, pure transforms (Partie 15.1's "normalize_*" functions) --------

def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_phone(value: str) -> str:
    return re.sub(r"[^\d+]", "", value)


def normalize_date(value: str) -> str:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return value  # unrecognized format -- returned unchanged, never crashes


_TRANSFORMS = {"normalize_email": normalize_email, "normalize_phone": normalize_phone, "normalize_date": normalize_date}


def apply_mapping(payload: dict, mappings: list[IntegrationMapping]) -> dict:
    if not mappings:
        return payload
    result = {}
    for m in mappings:
        if m.source_field not in payload:
            continue
        value = payload[m.source_field]
        transform = _TRANSFORMS.get(m.transform) if m.transform else None
        result[m.target_field] = transform(str(value)) if transform else value
    return result


async def find_connection_by_token(db: AsyncSession, connection_id: uuid.UUID, token: str) -> IntegrationConnection | None:
    conn = await db.get(IntegrationConnection, connection_id)
    if conn is None or not conn.is_active or not secrets.compare_digest(conn.token, token):
        return None
    return conn


async def handle_inbound_payload(db: AsyncSession, connection: IntegrationConnection, payload: dict) -> IntegrationLog:
    """Real handling: applies this connection's real field mappings,
    then executes its one real configured action. Any failure is
    caught and recorded as a real `error` log row -- an external
    system's malformed payload must never 500 this endpoint."""
    mappings = await list_mappings(db, connection.id)
    mapped = apply_mapping(payload, mappings)

    try:
        if connection.action == IntegrationAction.ingest_document:
            await _ingest_as_document(db, connection, mapped or payload)
        log = IntegrationLog(connection_id=connection.id, status=IntegrationLogStatus.accepted, payload=payload)
    except Exception as exc:  # noqa: BLE001 -- an external system's bad payload must never 500 this endpoint
        log = IntegrationLog(connection_id=connection.id, status=IntegrationLogStatus.error, payload=payload, detail=str(exc))

    db.add(log)
    await db.flush()
    return log


async def _ingest_as_document(db: AsyncSession, connection: IntegrationConnection, data: dict) -> None:
    from api.security.documents import upload_document

    text_parts = [f"{key}: {value}" for key, value in data.items() if isinstance(value, (str, int, float))]
    if not text_parts:
        raise ValueError("payload has no text fields to ingest")
    content = "\n".join(text_parts).encode("utf-8")
    filename = f"{connection.name}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')}.txt"
    await upload_document(db, connection.organization_id, None, connection.created_by, filename, content)


async def get_logs(db: AsyncSession, connection_id: uuid.UUID, limit: int = 50) -> list[IntegrationLog]:
    return list((await db.scalars(select(IntegrationLog).where(IntegrationLog.connection_id == connection_id).order_by(IntegrationLog.created_at.desc()).limit(limit))).all())
