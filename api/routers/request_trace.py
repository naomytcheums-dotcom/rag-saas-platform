"""GET /responses/{response_id}/trace: the whole story of one answer in a single read-only call (spec 13.5.12).

Same permission boundary as every other response-scoped read: `require_response_member` resolves the response and checks that the caller is a
member of its organization (a response of another organization answers 404, never its content).
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.models.response import Response
from api.security.citations import require_response_member
from api.services.request_trace import build_request_trace

router = APIRouter(tags=["request-trace"])


@router.get("/responses/{response_id}/trace")
async def get_request_trace(
    response_ctx: tuple[Response, OrganizationMember] = Depends(require_response_member), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    response, _caller = response_ctx
    return await build_request_trace(db, response)
