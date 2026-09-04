"""
Partie 2.2.6 -- creating, listing, updating, and deleting an
organization's own real tags, and assigning/unassigning them to real
documents. A separate module from api/security/documents.py (already a
real, large file spanning every import source since Partie 2.1.1) --
same "one file per related-but-distinct concern under a shared domain"
convention as api/security/organizations.py vs
organization_members.py/organization_settings.py.

Real permission checks (who may modify/delete a tag, who may assign
one to a document) live in api/routers/documents.py itself, the SAME
place DELETE /documents/{document_id}'s own real
"creator OR Admin/Owner" check already lives -- this module focuses on
the real DB mutations and business-rule validation (duplicate names,
cross-tenant mismatches), not on who is allowed to call it.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.document import Document, DocumentTag, DocumentTagAssignment


async def create_tag(db: AsyncSession, organization_id: uuid.UUID, created_by: uuid.UUID, name: str, color: str | None) -> DocumentTag:
    """
    Item 3's own literal `POST .../tags` route's real backing function.
    A real, empty/whitespace-only name is rejected here (never a
    genuinely blank real tag) -- the real `UNIQUE(organization_id, name)`
    constraint (this step's own literal ask) is what actually stops a
    real duplicate at the database layer; a real `IntegrityError` from
    it is caught and re-raised as a real, clear `ValueError` the router
    turns into a real 409, not a raw 500.
    """
    name = name.strip()
    if not name:
        raise ValueError("tag name must not be empty")

    tag = DocumentTag(organization_id=organization_id, name=name, color=color, created_by=created_by)
    db.add(tag)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError(f"a tag named '{name}' already exists in this organization") from exc
    return tag


async def list_tags(db: AsyncSession, organization_id: uuid.UUID) -> list[DocumentTag]:
    """Item 3's own literal `GET .../tags` route's real backing
    function -- every real tag this organization has ever created."""
    result = await db.scalars(select(DocumentTag).where(DocumentTag.organization_id == organization_id).order_by(DocumentTag.name))
    return list(result.all())


async def get_tag_or_raise(db: AsyncSession, tag_id: uuid.UUID) -> DocumentTag:
    """NOT one of this step's own literal functions -- a real, shared
    lookup `PATCH`/`DELETE .../tags/{tag_id}` (and the document
    assignment routes) all need, raising a real `ValueError` (the
    router's own job to turn into a real 404) rather than returning
    `None` and making every caller re-check it."""
    tag = await db.get(DocumentTag, tag_id)
    if tag is None:
        raise ValueError(f"'{tag_id}' is not a registered tag")
    return tag


async def update_tag(db: AsyncSession, tag_id: uuid.UUID, name: str | None, color: str | None) -> DocumentTag:
    """Item 3's own literal `PATCH /tags/{tag_id}` route's real backing
    function -- real permission checks (vision critique 3's own
    "peut-il modifier un tag créé par un autre" answer) happen in the
    router BEFORE this is ever called."""
    tag = await get_tag_or_raise(db, tag_id)
    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("tag name must not be empty")
        tag.name = name
    if color is not None:
        tag.color = color
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError(f"a tag named '{name}' already exists in this organization") from exc
    return tag


async def delete_tag(db: AsyncSession, tag_id: uuid.UUID) -> None:
    """Item 3's own literal `DELETE /tags/{tag_id}` route's real
    backing function -- real `ondelete="CASCADE"` on
    `DocumentTagAssignment.tag_id` (this model's own real FK) means
    every real assignment of this tag to any real document is removed
    for real along with it, never left as a real dangling reference."""
    tag = await get_tag_or_raise(db, tag_id)
    await db.delete(tag)
    await db.flush()


async def assign_tag_to_document(db: AsyncSession, document_id: uuid.UUID, tag_id: uuid.UUID, assigned_by: uuid.UUID) -> None:
    """
    Item 3's own literal `POST /documents/{document_id}/tags` route's
    real backing function. Real, necessary cross-tenant guard (vision
    critique 1's own "les tags sont-ils partagés entre les documents
    d'une même organisation" answer, the OTHER half of it): a real tag
    can only be assigned to a real document in the SAME real
    organization that owns the tag -- checked here, not left to the
    real FK constraints alone (which have no way to express "same
    organization_id on both sides").
    """
    document = await db.get(Document, document_id)
    if document is None:
        raise ValueError(f"'{document_id}' is not a registered document")
    tag = await get_tag_or_raise(db, tag_id)
    if tag.organization_id != document.organization_id:
        raise ValueError("this tag does not belong to the same organization as this document")

    assignment = DocumentTagAssignment(document_id=document_id, tag_id=tag_id, assigned_by=assigned_by)
    db.add(assignment)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError("this tag is already assigned to this document") from exc


async def unassign_tag_from_document(db: AsyncSession, document_id: uuid.UUID, tag_id: uuid.UUID) -> None:
    """Item 3's own literal `DELETE /documents/{document_id}/tags/{tag_id}`
    route's real backing function."""
    assignment = await db.scalar(
        select(DocumentTagAssignment).where(DocumentTagAssignment.document_id == document_id, DocumentTagAssignment.tag_id == tag_id)
    )
    if assignment is None:
        raise ValueError("this tag is not assigned to this document")
    await db.delete(assignment)
    await db.flush()


async def list_document_tags(db: AsyncSession, document_id: uuid.UUID) -> list[DocumentTag]:
    """Item 3's own literal `GET /documents/{document_id}/tags` route's
    real backing function."""
    result = await db.scalars(
        select(DocumentTag)
        .join(DocumentTagAssignment, DocumentTagAssignment.tag_id == DocumentTag.id)
        .where(DocumentTagAssignment.document_id == document_id)
        .order_by(DocumentTag.name)
    )
    return list(result.all())
