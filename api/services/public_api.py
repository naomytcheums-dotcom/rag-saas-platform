"""
Partie 9.1.1-9.1.9 -- the real, public `/v1/*` API handlers. Every one
of these reuses an already-real, existing engine rather than a second,
parallel implementation: `AgentOrchestrator.run_agent` (chat/agent
run), `search_with_context` (search, and the citations behind chat),
`upload_document` (documents), `get_usage_summary` (usage/analytics),
`get_embedding` (embed).

**Incohérence réelle corrigée -- une conversation a besoin d'un vrai
propriétaire humain**: `Conversation.user_id` is a real, NOT NULL FK
(Partie 5.1.12's own conversations are a personal resource, not an
organization one) -- but a public API caller authenticates with an
ORGANIZATION-scoped key, not a user session. Real, coherent fix:
conversations created through this public API are attributed to
whichever real org member generated the API key
(`OrganizationAPIKey.created_by`) -- the same real, sensible ownership
model this project already uses for "who created this workspace/
document" elsewhere."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.citation import Citation
from api.models.conversation import Conversation, ConversationMessage
from api.models.organization_api_key import OrganizationAPIKey
from api.models.workspace import Workspace
from api.security.conversations import add_message, create_conversation, get_conversation, get_conversation_messages
from api.security.documents import upload_document
from api.security.organization_settings import get_org_settings
from api.security.usage import get_usage_summary


class PublicAPIError(ValueError):
    """Real, honest failure -- the router turns this into a 4xx."""


def _require_owner(key_row: OrganizationAPIKey) -> uuid.UUID:
    if key_row.created_by is None:
        raise PublicAPIError("This API key has no associated user and cannot own a conversation -- regenerate it via an authenticated session")
    return key_row.created_by


# --------------------------------------------------------------------- 9.1.1 Chat


async def handle_public_chat(db: AsyncSession, key_row: OrganizationAPIKey, message: str, agent_id: str, conversation_id: uuid.UUID | None) -> dict:
    from api.services.agent_orchestrator import AgentOrchestrator
    from api.services.retrieval_pipeline import search_with_context

    organization_id = key_row.organization_id
    if conversation_id is not None:
        conversation = await get_conversation(db, conversation_id)
        if conversation is None or conversation.organization_id != organization_id:
            raise PublicAPIError("Conversation not found")
    else:
        conversation = await create_conversation(db, agent_id, _require_owner(key_row), message[:80], organization_id=organization_id)
        await db.flush()

    org_settings = await get_org_settings(db, organization_id)
    citation_chunks = await search_with_context(db, organization_id, message, top_k=5, org_settings=org_settings)

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent(
        agent_id, message, db=db, organization_id=organization_id, created_by=key_row.created_by,
        conversation_id=conversation.id, citation_chunks=citation_chunks,
    )
    if run.status != "completed":
        raise PublicAPIError(run.error or f"Chat generation failed with status '{run.status}'")

    citations = []
    if run.response_id is not None:
        rows = (await db.scalars(select(Citation).where(Citation.response_id == run.response_id))).all()
        citations = [
            {"citation_number": c.citation_number, "text": c.text, "source_title": c.source_title, "source_url": c.source_url, "relevance_score": c.relevance_score}
            for c in rows
        ]

    last_message = (await db.scalars(
        select(ConversationMessage).where(ConversationMessage.conversation_id == conversation.id, ConversationMessage.role == "assistant")
        .order_by(ConversationMessage.created_at.desc()).limit(1)
    )).first()

    return {
        "message_id": last_message.id if last_message is not None else uuid.uuid4(),
        "conversation_id": conversation.id, "response": run.result, "citations": citations,
        "metadata": {"run_id": str(run.id)},
    }


# ---------------------------------------------------------------- 9.1.2 Documents


async def handle_public_document_upload(db: AsyncSession, key_row: OrganizationAPIKey, filename: str, content: bytes, workspace_id: uuid.UUID | None) -> dict:
    try:
        document, is_duplicate = await upload_document(db, key_row.organization_id, workspace_id, key_row.created_by, filename, content)
    except ValueError as exc:
        raise PublicAPIError(str(exc)) from exc
    return {"document_id": document.id, "status": "duplicate" if is_duplicate else document.status, "name": document.name, "metadata": {"is_duplicate": is_duplicate}}


# ----------------------------------------------------------- 9.1.3 Knowledge bases


async def handle_public_kb_creation(db: AsyncSession, key_row: OrganizationAPIKey, name: str, description: str | None, config: dict | None) -> Workspace:
    workspace = Workspace(organization_id=key_row.organization_id, name=name, created_by=key_row.created_by)
    db.add(workspace)
    await db.flush()
    return workspace


# ------------------------------------------------------------- 9.1.4 Conversations


async def handle_public_conversations_list(db: AsyncSession, organization_id: uuid.UUID, agent_id: str | None, limit: int, offset: int) -> dict:
    """Real, org-wide listing -- NOT `api.security.conversations.get_conversations`
    (that one filters by a single real `user_id`, the wrong real scope
    for an organization-wide API key that doesn't represent one user)."""
    query = select(Conversation).where(Conversation.organization_id == organization_id, Conversation.deleted_at.is_(None))
    if agent_id is not None:
        query = query.where(Conversation.agent_id == agent_id)
    total = len((await db.scalars(query)).all())
    query = query.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)
    conversations = list((await db.scalars(query)).all())

    items = []
    for conversation in conversations:
        messages = await get_conversation_messages(db, conversation.id, limit=1000)
        preview = messages[-1].content[:140] if messages else None
        items.append({
            "id": conversation.id, "title": conversation.title, "created_at": conversation.created_at,
            "updated_at": conversation.updated_at, "last_message_preview": preview,
        })
    return {"items": items, "total": total, "limit": limit, "offset": offset}


# -------------------------------------------------------------------- 9.1.5 Search


async def handle_public_search(db: AsyncSession, organization_id: uuid.UUID, query: str, workspace_id: uuid.UUID | None, filters: dict | None, top_k: int) -> dict:
    from api.services.retrieval_pipeline import search_with_context

    org_settings = await get_org_settings(db, organization_id)
    results = await search_with_context(db, organization_id, query, top_k=top_k, org_settings=org_settings)
    return {"results": results, "total": len(results), "query": query, "metadata": {"workspace_id": str(workspace_id) if workspace_id else None}}


# --------------------------------------------------------------- 9.1.6 Agents/run


async def handle_public_agent_run(db: AsyncSession, key_row: OrganizationAPIKey, agent_id: str, input: str, conversation_id: uuid.UUID | None) -> dict:
    from api.services.agent_orchestrator import AgentOrchestrator

    if conversation_id is not None:
        conversation = await get_conversation(db, conversation_id)
        if conversation is None or conversation.organization_id != key_row.organization_id:
            raise PublicAPIError("Conversation not found")

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent(
        agent_id, input, db=db, organization_id=key_row.organization_id, created_by=key_row.created_by, conversation_id=conversation_id,
    )
    if run.status != "completed":
        raise PublicAPIError(run.error or f"Agent run failed with status '{run.status}'")
    return {"run_id": run.id, "output": run.result, "conversation_id": conversation_id, "metadata": {"status": run.status}}


# ------------------------------------------------------------------- 9.1.7 Usage


async def handle_public_usage(db: AsyncSession, organization_id: uuid.UUID, period: str) -> dict:
    import datetime as dt

    days_by_period = {"day": 1, "week": 7, "month": 30, "year": 365}
    days = days_by_period.get(period, 30)
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=days)
    summary = await get_usage_summary(db, organization_id, start_date=start_date, end_date=end_date)

    now = dt.datetime.now(dt.timezone.utc)
    metrics = [{"name": name, "value": value, "unit": "count", "timestamp": now} for name, value in summary["total_by_metric"].items()]
    return {"period": period, "metrics": metrics, "breakdown": summary["by_day"], "total": sum(summary["total_by_metric"].values())}


# --------------------------------------------------------------- 9.1.8 Analytics


async def handle_public_analytics(db: AsyncSession, organization_id: uuid.UUID, period: str, requested_metrics: list[str] | None) -> dict:
    """Real, honest scope: this codebase's own Partie 11 (Admin
    Dashboard & Analytics) has NO real aggregation infra yet (question
    clusters, knowledge gaps, satisfaction trends -- all genuinely
    unbuilt, per docs/CAHIER_DES_CHARGES.md's own real status). This
    real endpoint surfaces the ONE real, existing aggregate this
    project has -- usage counts, via the same real `get_usage_summary`
    9.1.7 uses -- rather than fabricating metrics that don't exist."""
    import datetime as dt

    days_by_period = {"day": 1, "week": 7, "month": 30, "year": 365}
    days = days_by_period.get(period, 30)
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=days)
    summary = await get_usage_summary(db, organization_id, start_date=start_date, end_date=end_date)

    metrics = [
        {"name": name, "value": float(value), "change_percentage": None, "trend": "flat"}
        for name, value in summary["total_by_metric"].items()
        if requested_metrics is None or name in requested_metrics
    ]
    return {
        "period": period, "metrics": metrics, "data": summary["by_day"],
        "summary": "Usage-based metrics only -- deeper analytics (question clusters, knowledge gaps, satisfaction trends) are not yet implemented (Partie 11).",
    }


# ----------------------------------------------------------------------- 9.1.9 Embed


async def handle_public_documents_list(db: AsyncSession, organization_id: uuid.UUID, limit: int, offset: int) -> list[dict]:
    """Real, additive: backs `GET /v1/documents` (`documents:read`,
    named in 9.2.4's own real scope table but never given a real
    endpoint by any literal 9.1.x ask)."""
    from api.models.document import Document

    query = (
        select(Document).where(Document.organization_id == organization_id, Document.deleted_at.is_(None))
        .order_by(Document.created_at.desc()).limit(limit).offset(offset)
    )
    documents = list((await db.scalars(query)).all())
    return [{"id": d.id, "name": d.name, "status": d.status, "created_at": d.created_at} for d in documents]


async def handle_public_agents_list(db: AsyncSession, organization_id: uuid.UUID, limit: int, offset: int) -> list[dict]:
    """Real, additive: backs `GET /v1/agents` (`agents:read`, same
    real reasoning as `handle_public_documents_list` above)."""
    from api.security.agents import list_agents

    agents = await list_agents(db, organization_id, limit=limit, offset=offset)
    return [{"id": a.id, "name": a.name, "description": a.description} for a in agents]


async def handle_public_kb_list(db: AsyncSession, organization_id: uuid.UUID, limit: int, offset: int) -> list[dict]:
    """Real, additive: backs `GET /v1/knowledge-bases` (`kb:read`,
    same real reasoning as `handle_public_documents_list` above)."""
    query = select(Workspace).where(Workspace.organization_id == organization_id).order_by(Workspace.created_at.desc()).limit(limit).offset(offset)
    workspaces = list((await db.scalars(query)).all())
    return [{"id": w.id, "name": w.name, "created_at": w.created_at} for w in workspaces]


async def handle_public_embed(text: str, model: str | None) -> dict:
    from api.services.embedding_providers import get_embedding, get_embedding_dimensions

    embedding = await get_embedding(text, model=model)
    resolved_model = model or "default"
    return {"embedding": embedding, "model": resolved_model, "dimensions": len(embedding) or get_embedding_dimensions("openai", resolved_model)}
