"""
Hardening Mission (§15) -- the real HTTP surface for A2A (Agent2Agent):
until now `api/services/a2a_integration.py` held a real, unit-tested
`AgentExecutor` that NOTHING ever called (no route, not referenced by
api/main.py) -- UNWIRED. This router is the missing transport.

Two endpoints, both authenticated by an organization `X-API-Key` carrying
the `a2a:call` scope (an agent card is organization metadata and every
task is a paid LLM call, so neither is public):

- `GET  /a2a/{org_id}/.well-known/agent-card.json` -- discovery.
- `POST /a2a/{org_id}`                              -- A2A JSON-RPC.

`org_id` in the path MUST equal the key's own organization (404 otherwise,
never a distinguishable 403 -- same anti-enumeration convention as
require_org_member), so a key can never address another tenant.

Cost control (§6): every task passes the shared pre-flight guard
(`assert_org_can_spend` -- balance + daily/monthly caps, BYOK exempt) and
an org-level rate limit BEFORE any LLM call. Platform-funded tasks reserve a
flat, documented ESTIMATE under a credit-row lock before execution and commit
it only when the task succeeds (`A2A_TASK_CREDIT_COST` -- BeeAI does not expose
token usage, so a per-token debit is not possible here).

Honest scope: non-streaming, no push notifications, in-memory per-request
task store (the agent card advertises exactly that) -- see
a2a_integration.py's own top docstring.
"""

import uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from api.config import settings
from api.dependencies import get_db
from api.models.organization import Organization
from api.models.organization_api_key import OrganizationAPIKey
from api.security.organization_settings import get_org_settings
from api.security.public_api_auth import require_public_api_scope
from api.security.rate_limit import enforce_rate_limit
from api.services.a2a_integration import (
    A2ANotAvailableError,
    RagAgentExecutor,
    build_agent_card,
)
from api.services.billing_credits import (
    InsufficientCreditsError,
    SpendCapExceededError,
    assert_org_can_spend,
    deduct_credits,
)
from api.services.llm_byok import resolve_org_api_key
from api.services.llm_config import resolve_llm_config

router = APIRouter(prefix="/a2a", tags=["A2A"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _session_factory_for(db: AsyncSession):
    """`RagAgentExecutor` wants a session FACTORY; hand it the request's
    own session so the whole task shares one transaction boundary (and
    one test-overridable `get_db`) instead of opening a second pool
    connection behind the request's back."""

    @asynccontextmanager
    async def _factory():
        yield db

    return _factory


class _BilledRagAgentExecutor(RagAgentExecutor):
    async def execute(self, context, event_queue) -> None:
        async with self._db_session_factory() as db:
            org_settings = await get_org_settings(db, self._organization_id)
            provider = resolve_llm_config(org_settings)["provider"]
            uses_byok = await resolve_org_api_key(db, self._organization_id, provider)
            if uses_byok:
                await super().execute(context, event_queue)
                return
            await deduct_credits(db, self._organization_id, settings.A2A_TASK_CREDIT_COST, resource_type="a2a_task")
            try:
                await super().execute(context, event_queue)
            except Exception:
                await db.rollback()
                raise
            await db.commit()


async def _load_org_for_key(org_id: uuid.UUID, key_row: OrganizationAPIKey, db: AsyncSession) -> Organization:
    if key_row.organization_id != org_id:
        raise _NOT_FOUND
    org = await db.get(Organization, org_id)
    if org is None:
        raise _NOT_FOUND
    return org


@router.get("/{org_id}/.well-known/agent-card.json")
async def get_agent_card(
    org_id: uuid.UUID, key_row: OrganizationAPIKey = Depends(require_public_api_scope("a2a:call")), db: AsyncSession = Depends(get_db),
):
    org = await _load_org_for_key(org_id, key_row, db)
    try:
        card = build_agent_card(org.name)
        from google.protobuf.json_format import MessageToDict
    except (A2ANotAvailableError, ImportError) as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=f"A2A is not available on this deployment: {exc}") from exc
    return MessageToDict(card)


@router.post("/{org_id}")
async def a2a_jsonrpc(
    org_id: uuid.UUID, request: Request,
    key_row: OrganizationAPIKey = Depends(require_public_api_scope("a2a:call")), db: AsyncSession = Depends(get_db),
):
    org = await _load_org_for_key(org_id, key_row, db)

    await enforce_rate_limit(f"ratelimit:a2a:org:{org_id}", settings.A2A_RATE_LIMIT_MAX_ATTEMPTS, settings.A2A_RATE_LIMIT_WINDOW_SECONDS)

    org_settings = await get_org_settings(db, org_id)
    try:
        await assert_org_can_spend(
            db,
            org_id,
            org_settings,
            resolve_llm_config(org_settings)["provider"],
            minimum_credits=settings.A2A_TASK_CREDIT_COST,
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient AI credits -- add a credit pack or configure your own provider key (BYOK)") from exc
    except SpendCapExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Spend cap exceeded: {exc}") from exc

    try:
        from a2a.server.request_handlers import DefaultRequestHandler
        from a2a.server.routes.jsonrpc_dispatcher import JsonRpcDispatcher
        from a2a.server.tasks import InMemoryTaskStore

        card = build_agent_card(org.name)
    except (A2ANotAvailableError, ImportError) as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=f"A2A is not available on this deployment: {exc}") from exc

    executor = _BilledRagAgentExecutor(db_session_factory=_session_factory_for(db), organization_id=org_id)
    handler = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore(), agent_card=card)
    completed = False
    try:
        response = await JsonRpcDispatcher(request_handler=handler).handle_requests(request)
        completed = True
    finally:
        if not completed:
            await handler.aclose()

    existing_background = response.background

    async def close_handler() -> None:
        try:
            if existing_background is not None:
                await existing_background()
        finally:
            await handler.aclose()

    response.background = BackgroundTask(close_handler)
    return response
