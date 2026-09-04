"""
Partie 2.2.7 -- creating, listing, and restoring a document's own real
version history. Same "separate module for a related-but-distinct
concern" convention as api/security/document_tags.py.

Real permission checks (Member+ if the caller owns the document, or an
Admin/Owner override) live in api/routers/documents.py itself, the SAME
place DELETE /documents/{document_id}'s own real permission check
already lives.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.document import Document, DocumentVersion
from api.security.document_audit import ACTION_UPDATED, ACTION_VERSION_RESTORED, log_document_action
from api.services.document_storage import upload_document_file, validate_document_upload


async def create_document_version(
    db: AsyncSession, document_id: uuid.UUID, file_key: str, file_size: int,
    metadata: dict | None, created_by: uuid.UUID | None, file_type: str | None = None,
) -> DocumentVersion:
    """
    Item 3's own literal function -- assigns the real NEXT version
    number for this document (the current real max + 1, or 1 if this
    is the first real version ever created for it -- see
    api/models/document.py's own DocumentVersion docstring for why a
    document's own original upload has no version 1 automatically),
    then updates the LIVE Document's own real `file_key`/`file_size`
    (and `file_type`, if given) to match -- every existing reader
    (preview/metadata/process_document/download) keeps working
    unchanged on "whatever this document's current content is".
    """
    document = await db.get(Document, document_id)
    if document is None:
        raise ValueError(f"'{document_id}' is not a registered document")

    last_version_number = await db.scalar(select(func.max(DocumentVersion.version_number)).where(DocumentVersion.document_id == document_id))
    version_number = (last_version_number or 0) + 1

    version = DocumentVersion(
        document_id=document_id, version_number=version_number, file_key=file_key,
        file_size=file_size, metadata_json=metadata, created_by=created_by,
    )
    db.add(version)
    await db.flush()

    document.file_key = file_key
    document.file_size = file_size
    if file_type is not None:
        document.file_type = file_type
    document.current_version_id = version.id
    await db.flush()
    return version


async def create_document_version_from_upload(
    db: AsyncSession, document_id: uuid.UUID, filename: str, content: bytes, created_by: uuid.UUID,
) -> DocumentVersion:
    """
    NOT one of this step's own literal functions -- the real bridge
    `POST /documents/{document_id}/versions` calls, keeping
    `api/routers/documents.py` thin (no direct S3/validation calls in
    the router, the SAME convention every prior upload path in this
    codebase already follows -- `api/security/documents.py`'s own
    `upload_document`). Real content validation
    (`validate_document_upload`, completely unchanged -- the exact
    same real check every upload already gets) happens BEFORE any real
    S3 write, then `create_document_version` above does the real
    version-row-plus-live-Document update.
    """
    document = await db.get(Document, document_id)
    if document is None:
        raise ValueError(f"'{document_id}' is not a registered document")

    content_type = validate_document_upload(content, filename)
    file_key = upload_document_file(document.organization_id, document.id, filename, content, content_type)
    version = await create_document_version(db, document_id, file_key, len(content), None, created_by, file_type=content_type)
    # Partie 2.2.10 -- the ONE real shared choke point both
    # POST .../versions and POST .../replace go through, so logging
    # "updated" here (never inside restore_document_version below,
    # which never calls this function) gives exactly one real audit
    # entry per real action, never a double one for a real restore.
    await log_document_action(db, document_id, created_by, ACTION_UPDATED, metadata={"version_number": version.version_number})
    return version


async def get_document_version(db: AsyncSession, document_id: uuid.UUID, version_number: int) -> DocumentVersion:
    """Item 3's own literal function."""
    version = await db.scalar(
        select(DocumentVersion).where(DocumentVersion.document_id == document_id, DocumentVersion.version_number == version_number)
    )
    if version is None:
        raise ValueError(f"document '{document_id}' has no version {version_number}")
    return version


async def get_document_versions(db: AsyncSession, document_id: uuid.UUID) -> list[DocumentVersion]:
    """Item 3's own literal function -- every real version, most
    recent first."""
    result = await db.scalars(
        select(DocumentVersion).where(DocumentVersion.document_id == document_id).order_by(DocumentVersion.version_number.desc())
    )
    return list(result.all())


async def restore_document_version(db: AsyncSession, document_id: uuid.UUID, version_number: int, restored_by: uuid.UUID | None) -> DocumentVersion:
    """
    Item 3's own literal function -- a real "restore as a NEW version"
    (the same real pattern `git revert` uses, not `git reset`): copies
    the TARGET version's own real `file_key`/`file_size`/`metadata_json`
    into a BRAND NEW version at the top of history via
    `create_document_version` above, rather than rewinding/reusing the
    old `version_number` -- a real, clean, monotonic audit trail
    ("version 5 is a real restore of version 2's content"), and the
    exact same live-Document-update behavior every other new version
    already gets.
    """
    target = await get_document_version(db, document_id, version_number)
    version = await create_document_version(db, document_id, target.file_key, target.file_size, target.metadata_json, restored_by)
    await log_document_action(db, document_id, restored_by, ACTION_VERSION_RESTORED, metadata={"restored_from_version_number": version_number, "new_version_number": version.version_number})
    return version
