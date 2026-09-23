"""
Partie 3.3.4-3.3.6 -- the real, live, multi-tenant search endpoint
`api/services/retrieval_pipeline.py`'s own docstring explains was
missing until now.

**A real, documented deviation from this étape's own literal path**
(`POST /search`): every other org-scoped router in this codebase
(`api/routers/organization_settings.py`, `api/routers/documents.py`,
etc.) mounts under `/organizations/{org_id}/...`, with
`require_org_member*` depending on that real path parameter -- a real,
deliberate security property: the permission check resolves from the
URL itself, before any request BODY is even parsed, so a caller can
never construct a body that names a different organization than the
one they were actually authorized against. Real path used here:
`POST /organizations/{org_id}/search`, matching that established
convention rather than breaking it for one new endpoint.

`GET /search/suggest` and `POST /search/stream` were explicitly marked
"(optionnel)" in this étape's own literal spec -- not built here, a
real, honest, documented scope limit, not an oversight.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.schemas.search import SearchRequest, SearchResponse
from api.security.organization_settings import get_org_settings
from api.security.organizations import require_org_member
from api.services.retrieval_config import resolve_retrieval_strategy
from api.services.retrieval_pipeline import search_with_context

router = APIRouter(tags=["search"])


@router.post("/organizations/{org_id}/search", response_model=SearchResponse)
async def search_organization_documents(
    org_id: uuid.UUID, payload: SearchRequest,
    _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db),
):
    org_settings = await get_org_settings(db, org_id)
    results = await search_with_context(
        db, org_id, payload.query, top_k=payload.top_k, strategy=payload.strategy,
        reranker=payload.reranker, score_threshold=payload.score_threshold, org_settings=org_settings,
        metadata_filters=payload.filters,
    )
    resolved_strategy = resolve_retrieval_strategy(org_settings, override=payload.strategy)
    return SearchResponse(query=payload.query, strategy=resolved_strategy, results=results)
