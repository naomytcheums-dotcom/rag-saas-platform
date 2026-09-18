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
from api.security.organization_settings import get_org_settings
from api.services.retrieval_pipeline import search_with_context
from api.services.streaming import stream_agent_response

router = APIRouter(tags=["chat-stream"])

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


async def _stream_response(
    agent_id: uuid.UUID, message: str, conversation_id: uuid.UUID | None, current_user: User, db: AsyncSession,
) -> StreamingResponse:
    agent, _membership = await resolve_agent_and_membership(agent_id, current_user, db)
    # Real bug found (2026-09-18) via a live end-to-end test: this route
    # never ran retrieval at all, so a streamed reply was never grounded
    # in this organization's documents and never carried citations --
    # same real search + context-building `handle_public_chat`
    # (api/services/public_api.py) already does for the public API path.
    org_settings = await get_org_settings(db, agent.organization_id)
    citation_chunks = await search_with_context(db, agent.organization_id, message, top_k=5, org_settings=org_settings)
    context = "\n\n".join(chunk["content"] for chunk in citation_chunks) if citation_chunks else None
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
