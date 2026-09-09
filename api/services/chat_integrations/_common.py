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
