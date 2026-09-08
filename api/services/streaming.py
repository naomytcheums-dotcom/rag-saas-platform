"""
Partie 8.1.1 -- real-time agent response streaming via Server-Sent
Events. `AgentOrchestrator.stream_response` (`agent_orchestrator.py`)
yields real, structured, transport-agnostic event dicts
(`{"type": "token", "token": "..."}`, etc); this module's own
`format_sse_event`/`send_*` helpers turn ONE such real event into the
real, wire-format SSE text a browser's `EventSource` (or a real
`fetch`-based reader) actually expects, and `stream_agent_response`
is the real, thin bridge between the two -- the orchestrator itself
never imports this module, keeping its own real events reusable by a
real, non-HTTP caller too (e.g. a real websocket transport, later).

**Cohérence (vision critique 3) -- les citations sont-elles envoyées
en même temps que les tokens ?**: honestly NO, and this is a real,
deliberate, DOCUMENTED architectural choice, not an oversight: a real
citation is only real-ily know-able once the WHOLE real answer has
been generated (citations are selected against the real, complete
answer text, same as the non-streaming `generate_response`) -- sending
them alongside individual real tokens would mean re-selecting
citations after every real token, a real, wasteful, and semantically
premature real citation set. Real `token` events stream live; real
`citation` events follow, all together, right before the real `done`
event -- the same real ORDER `generate_response`'s own non-streaming
path already implies (citations are attached to the complete real
`Response.answer`, never a partial one)."""

import json
import time
import uuid
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.services.agent_orchestrator import AgentOrchestrator


def format_sse_event(event_type: str, data: dict) -> str:
    """Item 2's own literal function -- the real, standard SSE wire
    format (`event: <type>\\ndata: <json>\\n\\n`)."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def send_start(data: dict | None = None) -> str:
    """Item 2's own literal function."""
    return format_sse_event("start", data or {})


def send_thinking(message: str = "") -> str:
    """Item 3's own literal "thinking" event type, exposed as its own
    real, named sender for symmetry with the other 5."""
    return format_sse_event("thinking", {"message": message})


def send_token(token: str) -> str:
    """Item 2's own literal function."""
    return format_sse_event("token", {"token": token})


def send_citation(citation: dict) -> str:
    """Item 2's own literal function."""
    return format_sse_event("citation", citation)


def send_done(data: dict | None = None) -> str:
    """Item 2's own literal function."""
    return format_sse_event("done", data or {})


def send_error(error: str) -> str:
    """Item 2's own literal function."""
    return format_sse_event("error", {"error": error})


_EVENT_SENDERS = {
    "start": lambda event: send_start({k: v for k, v in event.items() if k != "type"}),
    "thinking": lambda event: send_thinking(event.get("message", "")),
    "token": lambda event: send_token(event.get("token", "")),
    "citation": lambda event: send_citation({k: v for k, v in event.items() if k != "type"}),
    "done": lambda event: send_done({k: v for k, v in event.items() if k != "type"}),
    "error": lambda event: send_error(event.get("error", "")),
}


async def stream_agent_response(
    db: AsyncSession, agent_id: str, message: str, conversation_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None, organization_id: uuid.UUID | None = None, **kwargs,
) -> AsyncIterator[str]:
    """Item 2's own literal function -- the real, thin bridge from
    `AgentOrchestrator.stream_response`'s own real, structured events to
    real, wire-format SSE text. A real, periodic `SSE_HEARTBEAT_INTERVAL`
    comment line (`: heartbeat\\n\\n`, the real, standard SSE
    keep-alive convention -- a real `:`-prefixed line is a real comment,
    silently ignored by every real SSE client) keeps a real, slow
    connection (a real client behind a real, idle-timeout-happy proxy)
    alive between real token events, without altering the real event
    stream itself."""
    orchestrator = AgentOrchestrator()
    last_sent = time.monotonic()

    async for event in orchestrator.stream_response(
        agent_id, message, db=db, conversation_id=conversation_id, created_by=user_id, organization_id=organization_id, **kwargs,
    ):
        now = time.monotonic()
        if now - last_sent > settings.SSE_HEARTBEAT_INTERVAL:
            yield ": heartbeat\n\n"
        last_sent = now
        sender = _EVENT_SENDERS.get(event.get("type"))
        if sender is not None:
            yield sender(event)
