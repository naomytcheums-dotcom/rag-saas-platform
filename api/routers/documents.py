"""
Partie 2.1.1/2.1.10/2.1.11/2.1.12/2.1.13/2.1.14/2.1.15 -- uploading,
importing from a URL (or in bulk from a sitemap, from a GitHub
repository's files, from a GitHub repository's issues, from a Google
Drive folder/file, or a Google Doc/Sheet/Slide), listing, viewing, and
deleting an organization's documents.

Seven of these ten endpoints are org-scoped (`/organizations/{org_id}/
documents`[`/url`|`/sitemap`|`/github/repo`|`/github/issues`|
`/google-drive`|`/google-docs`], same `require_org_member*`
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
reach) -- the SAME rule applies to importing from a URL, a sitemap, a
GitHub repository, a GitHub repository's issues, a Google Drive
folder/file, or a Google Doc/Sheet/Slide, a real write just like a
file upload is. DELETE is Member+ if the caller uploaded the document
themselves, OR Admin/Owner as an administrative override -- a plain
Member can't delete someone ELSE's document.
"""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.document import Document
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.schemas.documents import (
    ConfluenceImportRequest,
    ConfluenceImportResponse,
    DocumentBatchUploadResponse,
    DocumentBatchUploadResult,
    DocumentListResponse,
    DocumentResponse,
    DocumentUrlImportRequest,
    GitHubIssuesImportRequest,
    GitHubIssuesImportResponse,
    GitHubRepoImportRequest,
    GitHubRepoImportResponse,
    GoogleDocImportRequest,
    GoogleDocImportResponse,
    GoogleDriveImportRequest,
    GoogleDriveImportResponse,
    NotionImportRequest,
    NotionImportResponse,
    OneDriveImportRequest,
    OneDriveImportResponse,
    SitemapImportRequest,
    SitemapImportResponse,
)
from api.security.documents import (
    import_document_from_url,
    start_confluence_import,
    start_document_batch_upload,
    start_github_issues_import,
    start_github_repo_import,
    start_google_doc_import,
    start_google_drive_import,
    start_notion_import,
    start_onedrive_import,
    start_sitemap_import,
    upload_document,
    validate_upload_batch,
)
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


@router.post("/organizations/{org_id}/documents/batch", response_model=DocumentBatchUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_documents_batch(
    org_id: uuid.UUID, files: list[UploadFile] = File(...), workspace_id: uuid.UUID | None = None,
    _caller: OrganizationMember = Depends(require_org_member_excluding_viewer),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Partie 2.2.1, item 1's own literal ask -- a SEPARATE, dedicated
    path rather than a literal modification of POST .../documents above
    (see api/security/documents.py's own Partie 2.2.1 section docstring
    for why: a real multi-file response, one outcome PER file, cannot
    be the same shape as a single upload's own bare DocumentResponse,
    and every existing single-upload caller/test keeps working
    completely unchanged this way). 202 Accepted -- nothing is durably
    stored yet when this returns; only the per-file CONTENT check
    (vision critique 3/4's own answer) runs synchronously here, real S3
    upload is deferred to Celery (vision critique 2's own answer)."""
    file_payloads = [(f.filename or "document", await f.read()) for f in files]
    try:
        validate_upload_batch(file_payloads)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        results = await start_document_batch_upload(db, org_id, workspace_id, current_user.id, file_payloads)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.commit()
    return DocumentBatchUploadResponse(
        results=[DocumentBatchUploadResult(filename=r["filename"], accepted=r["error"] is None, error=r["error"]) for r in results],
        scheduled=sum(1 for r in results if r["error"] is None),
    )


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


@router.post("/organizations/{org_id}/documents/github/issues", response_model=GitHubIssuesImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_documents_from_github_issues(
    org_id: uuid.UUID, payload: GitHubIssuesImportRequest, workspace_id: uuid.UUID | None = None,
    _caller: OrganizationMember = Depends(require_org_member_excluding_viewer),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Partie 2.1.13, item 1's own literal route. 202 Accepted, same
    reasoning as the sitemap/GitHub-repo routes above -- nothing is
    created synchronously, the issues aren't even fetched yet. Only
    real, non-network validation (repo URL format, workspace ownership)
    happens here; `state` is already constrained to GitHub's own three
    real values at the schema layer (a real, structural 422 for
    anything else, see api/schemas/documents.py's own
    GitHubIssuesImportRequest docstring)."""
    try:
        owner, repo = await start_github_issues_import(
            db, org_id, workspace_id, current_user.id, str(payload.repo_url),
            payload.state, payload.since, payload.labels, payload.max_issues,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.commit()
    return GitHubIssuesImportResponse(owner=owner, repo=repo, status="scheduled")


@router.post("/organizations/{org_id}/documents/google-drive", response_model=GoogleDriveImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_documents_from_google_drive(
    org_id: uuid.UUID, payload: GoogleDriveImportRequest, workspace_id: uuid.UUID | None = None,
    _caller: OrganizationMember = Depends(require_org_member_excluding_viewer),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Partie 2.1.14, item 1's own literal route. 202 Accepted, same
    reasoning as every prior async import route above -- nothing is
    created synchronously, the Drive file/folder isn't even fetched
    yet. Only real, non-network validation (non-empty drive_id,
    workspace ownership) happens here; no OAuth credential is ever
    accepted in this request body -- see api/schemas/documents.py's own
    GoogleDriveImportRequest docstring for why."""
    try:
        drive_id = await start_google_drive_import(
            db, org_id, workspace_id, current_user.id, payload.drive_id, payload.patterns, payload.max_files,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.commit()
    return GoogleDriveImportResponse(drive_id=drive_id, status="scheduled")


@router.post("/organizations/{org_id}/documents/google-docs", response_model=GoogleDocImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_documents_from_google_docs(
    org_id: uuid.UUID, payload: GoogleDocImportRequest, workspace_id: uuid.UUID | None = None,
    _caller: OrganizationMember = Depends(require_org_member_excluding_viewer),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Partie 2.1.15, item 1's own literal route. 202 Accepted, same
    reasoning as every prior async import route above -- nothing is
    exported synchronously; the real doc_type isn't even confirmed yet.
    Accepts EITHER a single `document_url_or_id` OR a real
    `document_urls_or_ids` list (see api/schemas/documents.py's own
    GoogleDocImportRequest docstring), matching this step's own literal
    single-document/batch pair of processing functions with ONE route."""
    try:
        document_ids, mode = await start_google_doc_import(
            db, org_id, workspace_id, current_user.id,
            payload.document_url_or_id, payload.document_urls_or_ids, payload.export_format,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.commit()
    return GoogleDocImportResponse(document_ids=document_ids, mode=mode, status="scheduled")


@router.post("/organizations/{org_id}/documents/notion", response_model=NotionImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_documents_from_notion(
    org_id: uuid.UUID, payload: NotionImportRequest, workspace_id: uuid.UUID | None = None,
    _caller: OrganizationMember = Depends(require_org_member_excluding_viewer),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Partie 2.1.16, item 1's own literal route. 202 Accepted, same
    reasoning as every prior async import route above -- nothing is
    fetched synchronously; `kind`'s own guess isn't even confirmed
    against the real API yet. Only real, non-network validation (URL/id
    format, workspace ownership) happens here; no Notion token is ever
    accepted in this request body."""
    try:
        notion_id, kind = await start_notion_import(
            db, org_id, workspace_id, current_user.id, payload.url_or_id, payload.kind, payload.max_pages,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.commit()
    return NotionImportResponse(notion_id=notion_id, kind=kind, status="scheduled")


@router.post("/organizations/{org_id}/documents/confluence", response_model=ConfluenceImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_documents_from_confluence(
    org_id: uuid.UUID, payload: ConfluenceImportRequest, workspace_id: uuid.UUID | None = None,
    _caller: OrganizationMember = Depends(require_org_member_excluding_viewer),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Partie 2.1.17, item 1's own literal route. 202 Accepted, same
    reasoning as every prior async import route above -- nothing is
    fetched synchronously. Only real, non-network validation (URL/id
    format, workspace ownership) happens here; no Confluence token or
    base URL is ever accepted in this request body -- both are real,
    server-wide settings."""
    try:
        confluence_id, kind = await start_confluence_import(
            db, org_id, workspace_id, current_user.id, payload.url_or_id, payload.max_pages,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.commit()
    return ConfluenceImportResponse(confluence_id=confluence_id, kind=kind, status="scheduled")


@router.post("/organizations/{org_id}/documents/onedrive", response_model=OneDriveImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_documents_from_onedrive(
    org_id: uuid.UUID, payload: OneDriveImportRequest, workspace_id: uuid.UUID | None = None,
    _caller: OrganizationMember = Depends(require_org_member_excluding_viewer),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Partie 2.1.18, item 1's own literal route. 202 Accepted, same
    reasoning as every prior async import route above -- nothing is
    fetched synchronously; the OneDrive item isn't even confirmed to
    exist yet. Only real, non-network validation (non-empty folder_id,
    workspace ownership) happens here; no OAuth credential is ever
    accepted in this request body -- see api/schemas/documents.py's own
    OneDriveImportRequest docstring for why."""
    try:
        folder_id = await start_onedrive_import(
            db, org_id, workspace_id, current_user.id, payload.folder_id, payload.patterns, payload.max_files,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.commit()
    return OneDriveImportResponse(folder_id=folder_id, status="scheduled")


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
