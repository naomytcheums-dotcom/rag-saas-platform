"""Partie 8.1.1 -- real-time agent response streaming (Server-Sent
Events). Both real routes resolve the real `Agent` + the caller's real
organization membership together (`resolve_agent_and_membership`,
`api/security/agents.py`) -- any real role may stream a chat response,
same real tier as reading/using an agent elsewhere in this codebase.

**Robustesse (vision critique 2) -- que se passe-t-il si le client se
déconnecte ?**: Starlette's own real `StreamingResponse` already
detects a real client disconnect (the real ASGI `http.disconnect`
message) and stops iterating the real generator -- `AgentOrchestrator.stream_response`'s
own real `finally`-free design means a real, in-flight LLM stream call
keeps running server-side until it naturally finishes (the same real,
honest limit `run_agent`'s own top docstring already documents for
cross-process cancellation: real, server-side cancellation of an
already-dispatched real LLM call needs its own, separate real
mechanism, not fabricated here)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from api.dependencies import get_current_user, get_db
from api.models.user import User
from api.schemas.chat_stream import ChatStreamRequest
from api.security.agents import resolve_agent_and_membership
from api.security.conversations import require_conversation_for_stream
from api.security.organization_settings import get_org_settings
from api.services.agent_citation_required import format_citation_required_response, get_citation_required_message
from api.services.agent_context_only import format_context_only_response, get_context_only_message
from api.services.retrieval_pipeline import build_llm_context, search_with_context
from api.services.streaming import send_done, send_start, send_token, stream_agent_response

router = APIRouter(tags=["chat-stream"])

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


async def _no_context_refusal(db: AsyncSession, agent, citation_chunks: list[dict]) -> str | None:
    """The agent's own refusal text when it is configured to answer only from sources (`citation_required` or
    `answer_only_from_context`, both opt-in) and retrieval found nothing; None when the model may answer."""
    if citation_chunks:
        return None
    if agent.citation_required:
        return format_citation_required_response(await get_citation_required_message(db, agent.id))
    if agent.answer_only_from_context:
        return format_context_only_response(await get_context_only_message(db, agent.id))
    return None


async def _refusal_events(message: str):
    yield send_start({"gated": True})
    yield send_token(message)
    yield send_done({"gated": True, "reason": "no_context"})


async def _stream_response(
    agent_id: uuid.UUID, message: str, conversation_id: uuid.UUID | None, current_user: User, db: AsyncSession,
) -> StreamingResponse:
    agent, membership = await resolve_agent_and_membership(agent_id, current_user, db)
    # Spec 1.3.7 -- per-user request limit on the costly chat path (after authorization, so a stranger cannot probe it). Fails open without Redis like every limiter here.
    from api.config import settings as app_settings  # noqa: PLC0415
    from api.security.rate_limit import enforce_rate_limit  # noqa: PLC0415

    await enforce_rate_limit(
        f"ratelimit:chat_stream:user:{current_user.id}", app_settings.CHAT_USER_RATE_LIMIT_MAX_ATTEMPTS, app_settings.CHAT_USER_RATE_LIMIT_WINDOW_SECONDS,
    )
    # Must run before retrieval and before the stream ever reads or
    # writes conversation history (TEN-001: cross-tenant write/read).
    if conversation_id is not None:
        await require_conversation_for_stream(db, conversation_id, current_user.id, agent.organization_id)
    # Real bug found (2026-09-18) via a live end-to-end test: this route
    # never ran retrieval at all, so a streamed reply was never grounded
    # in this organization's documents and never carried citations --
    # same real search + context-building `handle_public_chat`
    # (api/services/public_api.py) already does for the public API path.
    org_settings = await get_org_settings(db, agent.organization_id)
    # Hardening Mission, Phase 2 -- the real, confirmed missing half of
    # OPA/policy-aware retrieval (api.services.policy_aware_retrieval):
    # `search_with_context` already applies a real, caller-supplied
    # `user_context` to a real, opt-in OPA policy check (`search()`'s own
    # `resolve_policy_aware_retrieval_enabled` gate) -- but no real HTTP
    # caller ever built and passed one, so the feature had zero effect in
    # production even for an organization that fully configured OPA.
    # These are the real, standard subject attributes this authenticated
    # route actually has on hand -- an operator's own Rego policy decides
    # which of them (if any) it checks; never-populated here means never-
    # checkable there, not a guess at what any one operator's policy needs.
    user_context = {
        "user_id": str(current_user.id), "organization_id": str(agent.organization_id), "role": membership.role.value,
    }
    citation_chunks = await search_with_context(
        db, agent.organization_id, message, top_k=5, org_settings=org_settings, user_context=user_context,
    )
    context = build_llm_context(citation_chunks, org_settings)
    refusal = await _no_context_refusal(db, agent, citation_chunks)
    if refusal is not None:
        # RAG-004: decided BEFORE generation -- tokens already sent cannot be taken back, so an agent that must answer from sources
        # never calls the model when retrieval found nothing.
        return StreamingResponse(_refusal_events(refusal), media_type="text/event-stream", headers=_SSE_HEADERS)
    generator = stream_agent_response(
        db, str(agent.id), message, conversation_id=conversation_id, user_id=current_user.id, organization_id=agent.organization_id,
        context=context, citation_chunks=citation_chunks,
    )
    return StreamingResponse(generator, media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/chat/stream")
async def stream_chat_get_endpoint(
    agent_id: uuid.UUID = Query(...), message: str = Query(...), conversation_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Item 1's own literal `GET /chat/stream` -- real, query-string
    parameters (a real, native browser `EventSource` can only ever
    issue a real GET, with no real custom body)."""
    return await _stream_response(agent_id, message, conversation_id, current_user, db)


@router.post("/chat/stream")
async def stream_chat_post_endpoint(
    payload: ChatStreamRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Item 1's own literal `POST /chat/stream` -- for a real,
    `fetch`-based streaming client (reading a real `ReadableStream`
    body directly, not the native `EventSource` API), which CAN send a
    real JSON body."""
    return await _stream_response(payload.agent_id, payload.message, payload.conversation_id, current_user, db)
