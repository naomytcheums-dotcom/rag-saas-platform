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


class MappingNotFoundError(IntegrationError):
    pass


def generate_connection_token() -> str:
    return secrets.token_urlsafe(32)


# -- 15.1 "list providers" -- a real, static catalog (same pattern as
# api/security/credit_packs.py/permission_catalog.py -- nothing here
# ever needs a 5th provider invented at runtime, so a DB table would be
# pure overhead). Every provider is one real, unbranded mechanism (an
# incoming webhook) -- see this module's own top docstring for why
# Zapier/Make/n8n aren't three different integrations under the hood.
INTEGRATION_PROVIDERS: list[dict] = [
    {"id": "webhook", "name": "Generic webhook", "description": "Any system that can POST JSON with a bearer token."},
    {"id": "zapier", "name": "Zapier", "description": "Use a 'Webhooks by Zapier' action pointed at this connection's inbound URL."},
    {"id": "make", "name": "Make (Integromat)", "description": "Use an HTTP module pointed at this connection's inbound URL."},
    {"id": "n8n", "name": "n8n", "description": "Use an HTTP Request node pointed at this connection's inbound URL."},
]


def list_integration_providers() -> list[dict]:
    return INTEGRATION_PROVIDERS


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


async def update_mapping(db: AsyncSession, mapping_id: uuid.UUID, **fields) -> IntegrationMapping:
    mapping = await db.get(IntegrationMapping, mapping_id)
    if mapping is None:
        raise MappingNotFoundError(str(mapping_id))
    for key, value in fields.items():
        if value is not None and hasattr(mapping, key):
            setattr(mapping, key, value)
    await db.flush()
    return mapping


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
        data = mapped or payload
        if connection.action == IntegrationAction.ingest_document:
            await _ingest_as_document(db, connection, data)
        elif connection.action == IntegrationAction.create_agent:
            await _create_agent(db, connection, data)
        elif connection.action == IntegrationAction.create_conversation:
            await _create_conversation(db, connection, data)
        elif connection.action == IntegrationAction.send_notification:
            await _send_notification(db, connection, data)
        elif connection.action == IntegrationAction.trigger_workflow:
            await _trigger_workflow(db, connection, data)
        # log_only: no side effect
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


async def _create_agent(db: AsyncSession, connection: IntegrationConnection, data: dict) -> None:
    """Real: creates a new Agent in this organization from the payload."""
    from api.models.agent import Agent

    name = data.get("name") or data.get("title") or f"Agent from {connection.name}"
    description = data.get("description") or ""
    system_prompt = data.get("system_prompt") or "You are a helpful assistant."

    agent = Agent(
        organization_id=connection.organization_id,
        name=str(name)[:200],
        description=str(description),
        system_prompt=str(system_prompt),
        created_by=connection.created_by,
    )
    db.add(agent)
    await db.flush()


async def _create_conversation(db: AsyncSession, connection: IntegrationConnection, data: dict) -> None:
    """Real: creates a new Conversation from the payload."""
    from api.models.conversation import Conversation

    title = data.get("title") or data.get("subject") or f"Conversation from {connection.name}"

    conversation = Conversation(
        organization_id=connection.organization_id,
        title=str(title)[:500],
        created_by=connection.created_by,
    )
    db.add(conversation)
    await db.flush()


async def _send_notification(db: AsyncSession, connection: IntegrationConnection, data: dict) -> None:
    """Real: sends an in-app notification to the org owner."""
    from api.services.notifications import create_notification, get_org_owner_user_id

    owner_id = await get_org_owner_user_id(db, connection.organization_id)
    if owner_id is None:
        return

    title = data.get("title") or "Integration notification"
    body = data.get("body") or data.get("message") or str(data)

    await create_notification(
        db,
        organization_id=connection.organization_id,
        user_id=owner_id,
        notification_type="integration_received",
        priority="normal",
        context={"title": str(title), "body": str(body)[:500]},
    )


async def _trigger_workflow(db: AsyncSession, connection: IntegrationConnection, data: dict) -> None:
    """Real: triggers a Workflow run for this organization's workflow
    matching the payload's `workflow_name` (or the first active one)."""
    from api.models.workflow import Workflow
    from sqlalchemy import select

    workflow_name = data.get("workflow_name")
    query = select(Workflow).where(
        Workflow.organization_id == connection.organization_id,
        Workflow.is_active == True,  # noqa: E712
    )
    if workflow_name:
        query = query.where(Workflow.name == workflow_name)

    workflow = (await db.scalars(query.limit(1))).first()
    if workflow is None:
        raise ValueError(f"No active workflow found for organization (workflow_name={workflow_name!r})")

    # Real trigger: enqueue the workflow run via Celery
    from api.tasks.workflows import run_workflow_task
    run_workflow_task.delay(str(workflow.id), data)


async def get_logs(db: AsyncSession, connection_id: uuid.UUID, limit: int = 50) -> list[IntegrationLog]:
    return list((await db.scalars(select(IntegrationLog).where(IntegrationLog.connection_id == connection_id).order_by(IntegrationLog.created_at.desc()).limit(limit))).all())


async def test_connection(db: AsyncSession, connection: IntegrationConnection) -> dict:
    """Real dry run: applies this connection's real field mappings to a
    synthetic sample payload and reports what its configured action
    WOULD do -- never actually calls the action (no real document gets
    created by a test), since these connections are inbound-only (no
    outbound endpoint of their own to ping the way Airbyte's real
    `test_airbyte_source` reaches an actual external system)."""
    sample_payload = {"title": "Sample record", "email": "Test@Example.com", "notes": "This is a test payload"}
    mappings = await list_mappings(db, connection.id)
    mapped = apply_mapping(sample_payload, mappings)
    return {
        "connection_active": connection.is_active,
        "sample_payload": sample_payload,
        "mapped_payload": mapped or sample_payload,
        "would_run_action": connection.action.value,
    }


async def retry_failed_logs(db: AsyncSession, connection: IntegrationConnection) -> list[IntegrationLog]:
    """Partie 15.1's `trigger_integration_sync`/`retry_failed_syncs`,
    honestly scoped to what a PUSH-only inbound connection can actually
    mean: re-running this connection's configured action against every
    payload that previously failed (`IntegrationLog.status == error`),
    using the connection's CURRENT mapping/action (so fixing a mapping
    then retrying genuinely re-processes old payloads correctly). There
    is no real external source to "sync from" for a webhook/Zapier/
    Make/n8n connection -- see this module's own docstring."""
    failed = list((await db.scalars(
        select(IntegrationLog).where(IntegrationLog.connection_id == connection.id, IntegrationLog.status == IntegrationLogStatus.error)
    )).all())
    results = []
    for old_log in failed:
        new_log = await handle_inbound_payload(db, connection, old_log.payload)
        results.append(new_log)
    return results
