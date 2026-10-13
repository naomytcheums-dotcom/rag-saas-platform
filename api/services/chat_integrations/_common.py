"""Real, shared engine behind every one of Slack/Teams/Discord's own
`process_*_message` (Partie 9.4.1/9.4.2/9.4.3) -- all three literally
ask for their own bespoke message-processing function, but every one
of them does the SAME real thing: take inbound platform text, run it
through the SAME real chat engine `POST /v1/chat` and `POST
/widget/chat` already reuse (`handle_public_chat`,
api/services/public_api.py), and format the real result for that
platform. One real function here, three thin, platform-specific
wrappers around it -- not three copies of the same real logic."""

import uuid

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.public_api import PublicAPIError, handle_public_chat


async def run_chat_engine(db: AsyncSession, organization_id: uuid.UUID, created_by: uuid.UUID, agent_id: uuid.UUID, message: str, conversation_id: uuid.UUID | None) -> dict:
    """Returns `{"response": str, "citations": list[dict],
    "conversation_id": uuid.UUID}` on success, or `{"error": str}` --
    never raises, so a platform's own webhook handler can always
    format SOME real reply (including a real, honest error message)
    rather than crashing on an unhandled exception mid-conversation."""
    try:
        result = await handle_public_chat(db, organization_id, created_by, message, str(agent_id), conversation_id)
    except PublicAPIError as exc:
        return {"error": str(exc)}
    return {"response": result["response"], "citations": result["citations"], "conversation_id": result["conversation_id"]}


def format_citations_as_footnotes(citations: list[dict], max_citations: int = 3) -> str:
    """Shared, platform-agnostic citation formatting -- each
    platform's own `format_*_response` wraps this in its own real
    markup (Slack's `<url|title>`, Discord's bare markdown link,
    Teams' Adaptive Card facts)."""
    if not citations:
        return ""
    lines = [f"[{c['citation_number']}] {c.get('source_title') or 'Source'}" for c in citations[:max_citations]]
    return "\n".join(lines)


async def claim_inbound_event(db: AsyncSession, model, scope: dict, values: dict):
    """Idempotent intake of a webhook event. Slack retries an event it did not see acknowledged within 3 s, an `app_mention` arrives next to the
    `message` event of the same post, Discord's gateway bot redelivers after a reconnect: each must be answered ONCE.

    `scope` is the natural key of the event (integration + platform message id); returns `(row, created)`. Two deliveries racing on different
    workers are serialized by a transaction-scoped PostgreSQL advisory lock on that key (a unique index would need a migration over live log
    tables); the second one then finds the row of the first and gets `created=False`."""
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        key = f"{model.__tablename__}:" + ":".join(str(v) for v in scope.values())
        await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))
    existing = await db.scalar(select(model).where(*[getattr(model, column) == value for column, value in scope.items()]))
    if existing is not None:
        return existing, False
    row = model(**scope, **values)
    db.add(row)
    await db.flush()
    return row, True


def retry_after_seconds(response: httpx.Response, default: float = 1.0, ceiling: float = 10.0) -> float:
    """Seconds a platform asks us to wait after a 429 (`Retry-After` header, or Discord's `retry_after` JSON field)."""
    raw = response.headers.get("retry-after")
    if raw is None:
        try:
            raw = response.json().get("retry_after")
        except (ValueError, AttributeError):
            raw = None
    try:
        return min(max(float(raw), 0.0), ceiling)
    except (TypeError, ValueError):
        return default
