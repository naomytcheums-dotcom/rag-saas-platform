"""
Partie 6.1.1 -- real citation read endpoints. None of the 3 literal
paths carry `{org_id}`; each resolves its own resource AND the
caller's real organization role together (`require_response_member`/
`require_citation_member`/`require_document_citations_member`, all
Member+, same reasoning as every other individual-resource dependency
in this codebase).

Partie 6.1.2/6.1.3 -- every real citation returned here is enriched
with its real, LIVE document name/type AND page/section/heading
(`enrich_citation_with_document`/`enrich_citation_with_location`,
plural forms for the list endpoints) before being serialized, so a
real API caller always sees the current real values, not only the
denormalized snapshot from citation time. Real, deliberate scope: this
enrichment is NEVER committed back to the database here -- a real GET
must stay a real, honest read with no persistent side effect; only
THIS response's own real, in-memory objects are refreshed."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.citation import Citation
from api.models.document import Document
from api.models.organization import OrganizationMember
from api.models.response import Response
from api.schemas.citations import CitationResponse
from api.security.citations import require_citation_member, require_document_citations_member, require_response_member
from api.services.citation_documents import enrich_citation_with_document, enrich_citations_with_documents
from api.services.citation_location import enrich_citation_with_location, enrich_citations_with_location
from api.services.citations import get_citations_by_document, get_citations_by_response

router = APIRouter(tags=["citations"])


@router.get("/responses/{response_id}/citations", response_model=list[CitationResponse])
async def list_citations_by_response_endpoint(
    response_ctx: tuple[Response, OrganizationMember] = Depends(require_response_member), db: AsyncSession = Depends(get_db),
):
    response, _caller = response_ctx
    citations = await get_citations_by_response(db, response.id)
    citations = await enrich_citations_with_documents(db, citations)
    return await enrich_citations_with_location(db, citations)


@router.get("/citations/{citation_id}", response_model=CitationResponse)
async def get_citation_endpoint(
    citation_ctx: tuple[Citation, OrganizationMember] = Depends(require_citation_member), db: AsyncSession = Depends(get_db),
):
    citation, _caller = citation_ctx
    citation = await enrich_citation_with_document(db, citation)
    return await enrich_citation_with_location(db, citation)


@router.get("/documents/{document_id}/citations", response_model=list[CitationResponse])
async def list_citations_by_document_endpoint(
    document_ctx: tuple[Document, OrganizationMember] = Depends(require_document_citations_member), db: AsyncSession = Depends(get_db),
):
    document, _caller = document_ctx
    citations = await get_citations_by_document(db, document.id)
    citations = await enrich_citations_with_documents(db, citations)
    return await enrich_citations_with_location(db, citations)
