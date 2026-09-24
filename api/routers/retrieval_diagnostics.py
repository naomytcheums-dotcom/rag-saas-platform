"""
Phase 5, Étape 11 -- real, per-query retrieval diagnostics for an
organization's own LIVE (production) queries (see
api/models/retrieval_diagnostic.py's own docstring for the honest,
deliberate scope: final chunks + latency, recorded by
`api.services.generation.generate_response`'s own real call to
`record_retrieval_diagnostic`). Member+-readable, same tier as most
other org-scoped observability/config surfaces in this codebase --
diagnosing why an answer looked wrong doesn't need Admin.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.models.retrieval_diagnostic import RetrievalDiagnostic
from api.schemas.retrieval_diagnostic import RetrievalDiagnosticResponse
from api.security.permissions import require_permission
from api.security.organizations import require_org_member
from api.utils import MAX_PAGE_SIZE

router = APIRouter(tags=["retrieval-diagnostics"])


@router.get("/organizations/{org_id}/retrieval-diagnostics", response_model=list[RetrievalDiagnosticResponse])
async def list_retrieval_diagnostics_endpoint(
    org_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0),
    _caller: OrganizationMember = Depends(require_permission("documents:read")), db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(RetrievalDiagnostic)
        .where(RetrievalDiagnostic.organization_id == org_id)
        .order_by(RetrievalDiagnostic.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.all()
