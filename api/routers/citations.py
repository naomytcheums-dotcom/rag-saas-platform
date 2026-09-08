"""
Partie 6.1.1 -- real citation read endpoints. None of the 3 literal
paths carry `{org_id}`; each resolves its own resource AND the
caller's real organization role together (`require_response_member`/
`require_citation_member`/`require_document_citations_member`, all
Member+, same reasoning as every other individual-resource dependency
in this codebase).

Partie 6.1.2/6.1.3/6.1.4/6.1.5/6.1.6/6.1.7 -- every real citation
returned here is enriched with its real, LIVE document name/type,
page/section/heading, source URL, chunk ordinal, relevance label, AND
passage preview (`enrich_citation_with_document`/
`enrich_citation_with_location`/`enrich_citation_with_url`/
`enrich_citation_with_chunk`/`enrich_citation_with_relevance`/
`enrich_citation_with_passage`, plural forms for the list endpoints)
before being serialized, so a real API caller always sees the current
real values, not only the denormalized snapshot from citation time.
Real, deliberate scope: this enrichment is NEVER committed back to the
database here -- a real GET must stay a real, honest read with no
persistent side effect; only THIS response's own real, in-memory
objects are refreshed.

Partie 6.1.10 -- the 2 confidence endpoints below deliberately
RECOMPUTE confidence live from the response's own CURRENT citations
every time, rather than trusting `Response.confidence_score`'s own
stored, creation-time snapshot -- the same "live > snapshot" reasoning
as every enrichment above, particularly meaningful here since a
citation's own `document_id` can go real `NULL` after its source
document is later deleted (Partie 6.1.1's own `ondelete="SET NULL"`),
which should honestly lower a live-recomputed `reliability` factor,
not silently keep reporting stale, over-confident numbers.

Partie 6.2.4/6.2.6/6.2.7/6.2.8/6.2.9/6.2.10 -- `GET /responses/{response_id}`
below is a real, natural addition (none of those 6 étapes' own
literal asks requested a new endpoint) so their real, persisted
metrics are actually reachable through this same, already-established
`require_response_member` permission boundary -- unlike the confidence
endpoints above, this one returns the real, STORED creation-time
snapshot (see `ResponseDetailResponse`'s own docstring for why)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.citation import Citation
from api.models.document import Document
from api.models.organization import OrganizationMember
from api.models.response import Response
from api.schemas.citations import CitationResponse, ConfidenceFactorsResponse, ConfidenceResponse, ResponseDetailResponse
from api.security.citations import require_citation_member, require_document_citations_member, require_response_member
from api.services.citation_chunk import enrich_citation_with_chunk, enrich_citations_with_chunk
from api.services.citation_documents import enrich_citation_with_document, enrich_citations_with_documents
from api.services.citation_location import enrich_citation_with_location, enrich_citations_with_location
from api.services.citation_passage import enrich_citation_with_passage, enrich_citations_with_passage
from api.services.citation_relevance import enrich_citation_with_relevance, enrich_citations_with_relevance
from api.services.citation_url import enrich_citation_with_url, enrich_citations_with_url
from api.services.citations import get_citations_by_document, get_citations_by_response
from api.services.response_confidence import (
    calculate_confidence_factors, calculate_confidence_score, get_confidence_color, get_confidence_label,
)

router = APIRouter(tags=["citations"])


@router.get("/responses/{response_id}", response_model=ResponseDetailResponse)
async def get_response_endpoint(
    response_ctx: tuple[Response, OrganizationMember] = Depends(require_response_member),
):
    response, _caller = response_ctx
    return response


@router.get("/responses/{response_id}/citations", response_model=list[CitationResponse])
async def list_citations_by_response_endpoint(
    response_ctx: tuple[Response, OrganizationMember] = Depends(require_response_member), db: AsyncSession = Depends(get_db),
):
    response, _caller = response_ctx
    citations = await get_citations_by_response(db, response.id)
    citations = await enrich_citations_with_documents(db, citations)
    citations = await enrich_citations_with_location(db, citations)
    citations = await enrich_citations_with_url(db, citations)
    citations = await enrich_citations_with_chunk(db, citations)
    citations = await enrich_citations_with_passage(db, citations)
    return enrich_citations_with_relevance(citations)


@router.get("/responses/{response_id}/confidence", response_model=ConfidenceResponse)
async def get_response_confidence_endpoint(
    response_ctx: tuple[Response, OrganizationMember] = Depends(require_response_member), db: AsyncSession = Depends(get_db),
):
    response, _caller = response_ctx
    citations = await get_citations_by_response(db, response.id)
    score = calculate_confidence_score(citations)
    return ConfidenceResponse(confidence_score=score, confidence_label=get_confidence_label(score), confidence_color=get_confidence_color(score))


@router.get("/responses/{response_id}/confidence/factors", response_model=ConfidenceFactorsResponse)
async def get_response_confidence_factors_endpoint(
    response_ctx: tuple[Response, OrganizationMember] = Depends(require_response_member), db: AsyncSession = Depends(get_db),
):
    response, _caller = response_ctx
    citations = await get_citations_by_response(db, response.id)
    return ConfidenceFactorsResponse(**calculate_confidence_factors(citations))


@router.get("/citations/{citation_id}", response_model=CitationResponse)
async def get_citation_endpoint(
    citation_ctx: tuple[Citation, OrganizationMember] = Depends(require_citation_member), db: AsyncSession = Depends(get_db),
):
    citation, _caller = citation_ctx
    citation = await enrich_citation_with_document(db, citation)
    citation = await enrich_citation_with_location(db, citation)
    citation = await enrich_citation_with_url(db, citation)
    citation = await enrich_citation_with_chunk(db, citation)
    citation = await enrich_citation_with_passage(db, citation)
    return enrich_citation_with_relevance(citation)


@router.get("/documents/{document_id}/citations", response_model=list[CitationResponse])
async def list_citations_by_document_endpoint(
    document_ctx: tuple[Document, OrganizationMember] = Depends(require_document_citations_member), db: AsyncSession = Depends(get_db),
):
    document, _caller = document_ctx
    citations = await get_citations_by_document(db, document.id)
    citations = await enrich_citations_with_documents(db, citations)
    citations = await enrich_citations_with_location(db, citations)
    citations = await enrich_citations_with_url(db, citations)
    citations = await enrich_citations_with_chunk(db, citations)
    citations = await enrich_citations_with_passage(db, citations)
    return enrich_citations_with_relevance(citations)
