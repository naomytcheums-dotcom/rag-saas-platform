"""
Partie 6.1.1 -- real permission resolution for the 3 literal citation
endpoints, none of which carry `{org_id}` in their own literal path
(`GET /responses/{response_id}/citations`, `GET /citations/{citation_id}`,
`GET /documents/{document_id}/citations`) -- same real "resolve the
resource AND the caller's real organization role together, 404 not 403
for a non-member" reasoning as every other individual-resource
dependency in this codebase (`api/security/agents.py`,
`api/security/workflows.py`)."""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.citation import Citation
from api.models.document import Document
from api.models.organization import OrganizationMember
from api.models.response import Response
from api.models.user import User

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _membership_for(organization_id: uuid.UUID, current_user: User, db: AsyncSession) -> OrganizationMember:
    membership = await db.scalar(
        select(OrganizationMember).where(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == current_user.id)
    )
    if membership is None:
        raise _NOT_FOUND
    return membership


async def require_response_member(
    response_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[Response, OrganizationMember]:
    response = await db.get(Response, response_id)
    if response is None:
        raise _NOT_FOUND
    return response, await _membership_for(response.organization_id, current_user, db)


async def require_citation_member(
    citation_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[Citation, OrganizationMember]:
    citation = await db.get(Citation, citation_id)
    if citation is None:
        raise _NOT_FOUND
    response = await db.get(Response, citation.response_id)
    if response is None:
        raise _NOT_FOUND
    return citation, await _membership_for(response.organization_id, current_user, db)


async def require_document_citations_member(
    document_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[Document, OrganizationMember]:
    document = await db.get(Document, document_id)
    if document is None or document.deleted_at is not None:
        raise _NOT_FOUND
    return document, await _membership_for(document.organization_id, current_user, db)
