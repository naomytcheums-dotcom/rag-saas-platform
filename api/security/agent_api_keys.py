"""
Partie 5.3.10 -- the real `X-API-Key` header authentication dependency
for `POST /api/agents/run`, a genuinely different auth mechanism from
every other endpoint in this codebase (no JWT, no `get_current_user`).
"""

import uuid

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.agent import Agent
from api.models.agent_api_key import AgentAPIKey
from api.services.agent_api_keys import verify_api_key

_INVALID_KEY = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired API key")


async def require_agent_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"), db: AsyncSession = Depends(get_db),
) -> tuple[Agent, AgentAPIKey]:
    """Real dependency -- resolves the real `AgentAPIKey` row (verified,
    not revoked, not expired) AND the real `Agent` it belongs to
    together, so a route depending on this gets both without a second
    real DB round-trip. A soft-deleted agent behind an otherwise-valid
    key is treated the same as an invalid key (401, not 404 -- no
    reason to reveal to an API-key caller that an agent used to
    exist)."""
    key_row = await verify_api_key(db, x_api_key)
    if key_row is None:
        raise _INVALID_KEY

    agent = await db.get(Agent, key_row.agent_id)
    if agent is None or agent.deleted_at is not None:
        raise _INVALID_KEY

    return agent, key_row


def require_api_key_scope(scope: str):
    """Real, scope-gated dependency factory -- `"execute"` for
    `POST /api/agents/run` (item 3's own literal endpoint)."""

    async def _check(agent_ctx: tuple[Agent, AgentAPIKey] = Depends(require_agent_api_key)) -> tuple[Agent, AgentAPIKey]:
        agent, key_row = agent_ctx
        if scope not in key_row.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"This API key does not have the required {scope!r} scope")
        return agent, key_row

    return _check
