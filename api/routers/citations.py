"""
Partie 6.1.1 -- real citation read endpoints. None of the 3 literal
paths carry `{org_id}`; each resolves its own resource AND the
caller's real organization role together (`require_response_member`/
`require_citation_member`/`require_document_citations_member`, all
Member+, same reasoning as every other individual-resource dependency
in this codebase).
"""

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
from api.services.citations import get_citations_by_document, get_citations_by_response

router = APIRouter(tags=["citations"])


@router.get("/responses/{response_id}/citations", response_model=list[CitationResponse])
async def list_citations_by_response_endpoint(
    response_ctx: tuple[Response, OrganizationMember] = Depends(require_response_member), db: AsyncSession = Depends(get_db),
):
    response, _caller = response_ctx
    return await get_citations_by_response(db, response.id)


@router.get("/citations/{citation_id}", response_model=CitationResponse)
async def get_citation_endpoint(citation_ctx: tuple[Citation, OrganizationMember] = Depends(require_citation_member)):
    citation, _caller = citation_ctx
    return citation


@router.get("/documents/{document_id}/citations", response_model=list[CitationResponse])
async def list_citations_by_document_endpoint(
    document_ctx: tuple[Document, OrganizationMember] = Depends(require_document_citations_member), db: AsyncSession = Depends(get_db),
):
    document, _caller = document_ctx
    return await get_citations_by_document(db, document.id)
