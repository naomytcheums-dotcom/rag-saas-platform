"""
Partie 2.1.1/2.1.10/2.1.11/2.1.12 -- uploading, importing from a URL
(or in bulk from a sitemap, or from a GitHub repository), listing,
viewing, and deleting an organization's documents.

Four of these seven endpoints are org-scoped (`/organizations/{org_id}/
documents`[`/url`|`/sitemap`|`/github/repo`], same `require_org_member*`
dependency-injection shape as every other org-scoped router) and two
are NOT (`/documents/{document_id}`, this step's own literal paths) --
those look the document up FIRST, then check the CALLER's membership
in ITS organization manually (_get_document_and_membership below),
same 404-for-non-member-or-nonexistent anti-enumeration convention as
require_org_member itself, just applied by hand since there's no
org_id path parameter for FastAPI to resolve a Depends() against.

POST is Owner/Admin/Manager/Member -- explicitly NOT Viewer (see
api/security/organizations.py's require_org_member_excluding_viewer,
built for exactly this: a write endpoint Viewer's own role shouldn't
reach) -- the SAME rule applies to importing from a URL, a sitemap, or
a GitHub repository, a real write just like a file upload is. DELETE
is Member+ if the caller uploaded the document themselves, OR
Admin/Owner as an administrative override -- a plain Member can't
delete someone ELSE's document.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.document import Document
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.schemas.documents import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUrlImportRequest,
    GitHubRepoImportRequest,
    GitHubRepoImportResponse,
    SitemapImportRequest,
    SitemapImportResponse,
)
from api.security.documents import import_document_from_url, start_github_repo_import, start_sitemap_import, upload_document
from api.security.organizations import require_org_member, require_org_member_excluding_viewer
from api.services.document_storage import delete_document_file

router = APIRouter(tags=["documents"])


def _to_response(row: Document) -> DocumentResponse:
    return DocumentResponse(
        id=row.id, organization_id=row.organization_id, workspace_id=row.workspace_id, name=row.name,
        file_size=row.file_size, file_type=row.file_type, status=row.status, metadata=row.metadata_json,
        source_url=row.source_url,
        created_by=row.created_by, created_at=row.created_at, updated_at=row.updated_at, processed_at=row.processed_at,
    )


async def _get_document_and_membership(db: AsyncSession, document_id: uuid.UUID, current_user: User) -> tuple[Document, OrganizationMember]:
    """Shared by GET/DELETE /documents/{document_id} -- looks up the
    document, then the caller's membership in ITS organization. 404 for
    both "no such document" and "you're not a member of the
    organization that owns it", collapsed into one response so a
    non-member can't use this endpoint to probe which document ids
    exist (same anti-enumeration reasoning as require_org_member)."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    document = await db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise not_found

    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == document.organization_id, OrganizationMember.user_id == current_user.id
        )
    )
    if membership is None:
        raise not_found
    return document, membership


@router.post("/organizations/{org_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    org_id: uuid.UUID, file: UploadFile, workspace_id: uuid.UUID | None = None,
    _caller: OrganizationMember = Depends(require_org_member_excluding_viewer),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    try:
        document = await upload_document(db, org_id, workspace_id, current_user.id, file.filename or "document.pdf", content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    await db.commit()
    await db.refresh(document)
    return _to_response(document)


@router.post("/organizations/{org_id}/documents/url", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document_from_url(
    org_id: uuid.UUID, payload: DocumentUrlImportRequest, workspace_id: uuid.UUID | None = None,
    _caller: OrganizationMember = Depends(require_org_member_excluding_viewer),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Partie 2.1.10, item 1's own literal route. Only cheap,
    non-network validation (URL format/scheme) happens here -- the real
    accessibility/robots.txt/fetch all happen asynchronously afterward
    (api/security/documents.py's own process_url_document, run by
    Celery), so this returns fast even for a target that turns out to
    be slow or unreachable."""
    try:
        document = await import_document_from_url(db, org_id, workspace_id, current_user.id, str(payload.url))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.commit()
    await db.refresh(document)
    return _to_response(document)


@router.post("/organizations/{org_id}/documents/sitemap", response_model=SitemapImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_documents_from_sitemap(
    org_id: uuid.UUID, payload: SitemapImportRequest, workspace_id: uuid.UUID | None = None,
    _caller: OrganizationMember = Depends(require_org_member_excluding_viewer),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Partie 2.1.11, item 1's own literal route. 202 Accepted, not 201
    Created -- unlike a single upload or URL import, nothing is
    actually created yet by the time this response is sent: the
    sitemap itself isn't even fetched until the real Celery task runs
    (vision critique Q2's own answer). Only real, non-network
    validation (sitemap URL format, workspace ownership) happens here."""
    try:
        normalized_url = await start_sitemap_import(
            db, org_id, workspace_id, current_user.id, str(payload.url), payload.filters, payload.max_urls,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.commit()
    return SitemapImportResponse(sitemap_url=normalized_url, status="scheduled")


@router.post("/organizations/{org_id}/documents/github/repo", response_model=GitHubRepoImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_documents_from_github_repo(
    org_id: uuid.UUID, payload: GitHubRepoImportRequest, workspace_id: uuid.UUID | None = None,
    _caller: OrganizationMember = Depends(require_org_member_excluding_viewer),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Partie 2.1.12, item 1's own literal route. 202 Accepted, same
    reasoning as the sitemap route above -- nothing is created
    synchronously, the repository isn't even fetched yet. Only real,
    non-network validation (repo URL format, workspace ownership)
    happens here; no GitHub token is ever accepted in this request body
    -- see api/schemas/documents.py's own GitHubRepoImportRequest
    docstring for why."""
    try:
        owner, repo = await start_github_repo_import(
            db, org_id, workspace_id, current_user.id, str(payload.repo_url), payload.file_patterns, payload.max_files,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.commit()
    return GitHubRepoImportResponse(owner=owner, repo=repo, status="scheduled")


@router.get("/organizations/{org_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db),
):
    rows = (await db.scalars(
        select(Document).where(Document.organization_id == org_id).order_by(Document.created_at.desc())
    )).all()
    return DocumentListResponse(items=[_to_response(row) for row in rows])


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    document, _membership = await _get_document_and_membership(db, document_id, current_user)
    return _to_response(document)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    document, membership = await _get_document_and_membership(db, document_id, current_user)

    is_owner_of_document = document.created_by == current_user.id
    is_org_admin_or_owner = membership.role in (OrganizationRole.owner, OrganizationRole.admin)
    if membership.role == OrganizationRole.viewer or not (is_owner_of_document or is_org_admin_or_owner):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete documents you uploaded yourself")

    await db.execute(delete(Document).where(Document.id == document.id))
    await db.commit()

    delete_document_file(document.file_key)  # best-effort, never blocks the response
    return {"message": "Document deleted"}
