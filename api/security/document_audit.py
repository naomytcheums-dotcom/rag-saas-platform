"""
Partie 2.2.10 -- recording and retrieving a document's own real
history of actions (upload, replace, soft delete, reindex, tag add/
remove, version restore). A separate module from
`api/security/documents.py`, `document_tags.py`, and
`document_versions.py` -- same "one file per related-but-distinct
concern" convention already established for those.

**Real, fixed action names this codebase actually produces** (this
step's own literal list): `created`, `updated`, `deleted`, `reindexed`,
`tag_added`, `tag_removed`, `version_restored`. `restored` (undelete
from a real soft delete) is this step's own literal 8th action name --
NOT currently produced anywhere in this codebase, a real, honest gap
stated plainly: Partie 2.2.8's own module docstring already states its
own real scope limitation ("a real undelete/restore-from-trash
endpoint was not asked for and is not built") -- there is genuinely no
real code path that could call `log_document_action(..., "restored")`
honestly yet. The real action name is still defined here (in
`DOCUMENT_ACTIONS` below) so a future real undelete feature has
exactly one real place to plug into, not a name invented on the spot
later.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.document import DocumentAuditLog

# Real, fixed action vocabulary -- see this module's own docstring for
# which of these this codebase actually produces today.
ACTION_CREATED = "created"
ACTION_UPDATED = "updated"
ACTION_DELETED = "deleted"
ACTION_RESTORED = "restored"
ACTION_REINDEXED = "reindexed"
ACTION_TAG_ADDED = "tag_added"
ACTION_TAG_REMOVED = "tag_removed"
ACTION_VERSION_RESTORED = "version_restored"

DOCUMENT_ACTIONS = (
    ACTION_CREATED, ACTION_UPDATED, ACTION_DELETED, ACTION_RESTORED,
    ACTION_REINDEXED, ACTION_TAG_ADDED, ACTION_TAG_REMOVED, ACTION_VERSION_RESTORED,
)


async def log_document_action(
    db: AsyncSession, document_id: uuid.UUID, user_id: uuid.UUID | None, action: str,
    changes: dict | None = None, metadata: dict | None = None,
) -> DocumentAuditLog:
    """
    Item 2's own literal function -- a real, plain INSERT, deliberately
    NOT wrapped in a best-effort try/except (see
    `api/models/document.py`'s own `DocumentAuditLog` docstring for
    why: this shares the SAME real transaction as the action it
    records, on purpose). Callers pass the exact same `user_id` they
    already have on hand (a function's own `created_by`/`assigned_by`/
    `deleted_by`/etc. parameter) -- no new lookup, no new parameter
    threading beyond what each real caller already has.
    """
    entry = DocumentAuditLog(document_id=document_id, action=action, user_id=user_id, changes=changes, metadata_json=metadata)
    db.add(entry)
    await db.flush()
    return entry


async def get_document_history(db: AsyncSession, document_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[DocumentAuditLog]:
    """Item 2's own literal function -- real, paginated history, most
    recent first."""
    result = await db.scalars(
        select(DocumentAuditLog)
        .where(DocumentAuditLog.document_id == document_id)
        .order_by(DocumentAuditLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.all())
