"""
Partie 5.1.10 -- item 2's own literal functions:
`request_human_approval`/`approve_human_request`/`reject_human_request`/
`get_pending_approvals`/`get_approval_status`/`check_approval_expired`.

**`requires_human_approval(tool_name)`, a real, additional function**
(not literally named by this étape, but needed to make item 5's own
literal `HUMAN_APPROVAL_REQUIRED_TOOLS` default list actually mean
something): `True` only when `HUMAN_APPROVAL_ENABLED` is on AND
`tool_name` is in that real, configured list."""

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.human_approval import HumanApproval, HumanApprovalStatus


def requires_human_approval(tool_name: str) -> bool:
    return settings.HUMAN_APPROVAL_ENABLED and tool_name in settings.HUMAN_APPROVAL_REQUIRED_TOOLS


async def request_human_approval(
    db: AsyncSession, agent_run_id: uuid.UUID, tool_name: str, params: dict, requested_by: uuid.UUID | None,
    *, organization_id: uuid.UUID | None = None,
) -> HumanApproval:
    """Item 2's own literal function -- real expiry, `HUMAN_APPROVAL_EXPIRY`
    seconds from now (1h by default)."""
    now = dt.datetime.now(dt.timezone.utc)
    approval = HumanApproval(
        agent_run_id=agent_run_id, organization_id=organization_id, tool_name=tool_name, params=params,
        status=HumanApprovalStatus.pending.value, requested_by=requested_by,
        requested_at=now, expires_at=now + dt.timedelta(seconds=settings.HUMAN_APPROVAL_EXPIRY),
    )
    db.add(approval)
    await db.flush()
    return approval


def _as_aware_utc(value: dt.datetime) -> dt.datetime:
    """Real, necessary normalization: the fast SQLite suite's own
    `DateTime(timezone=True)` columns silently round-trip as
    timezone-NAIVE (SQLite has no native timezone-aware datetime type;
    only real Postgres actually preserves the offset) -- comparing a
    naive value against `dt.datetime.now(dt.timezone.utc)` directly
    raises `TypeError`. Every value this codebase ever writes here is
    already UTC, so a naive read-back is safely re-labeled UTC, not
    silently misinterpreted as local time."""
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


async def _resolve_if_expired(db: AsyncSession, approval: HumanApproval) -> HumanApproval:
    """Real, shared lazy-expiry check -- a `pending` request whose
    `expires_at` has passed is transitioned to `expired` the moment
    anything reads or acts on it, rather than needing a real, separate
    background sweep."""
    if approval.status == HumanApprovalStatus.pending.value and dt.datetime.now(dt.timezone.utc) >= _as_aware_utc(approval.expires_at):
        approval.status = HumanApprovalStatus.expired.value
        await db.flush()
    return approval


async def approve_human_request(db: AsyncSession, approval_id: uuid.UUID, approved_by: uuid.UUID | None, comment: str | None = None) -> HumanApproval | None:
    """Item 2's own literal function -- `None` for an unknown id;
    real, unchanged rejection of a non-pending request (already
    approved/rejected/expired) via the returned row's own `status`
    still reading something other than `approved` -- the caller can
    tell nothing happened by checking that."""
    approval = await db.get(HumanApproval, approval_id)
    if approval is None:
        return None
    approval = await _resolve_if_expired(db, approval)
    if approval.status != HumanApprovalStatus.pending.value:
        return approval

    approval.status = HumanApprovalStatus.approved.value
    approval.approved_by = approved_by
    approval.approved_at = dt.datetime.now(dt.timezone.utc)
    approval.comment = comment
    await db.flush()
    return approval


async def reject_human_request(db: AsyncSession, approval_id: uuid.UUID, approved_by: uuid.UUID | None, comment: str | None = None) -> HumanApproval | None:
    """Item 2's own literal function -- same real "no-op on a
    non-pending request" behavior as approve_human_request above."""
    approval = await db.get(HumanApproval, approval_id)
    if approval is None:
        return None
    approval = await _resolve_if_expired(db, approval)
    if approval.status != HumanApprovalStatus.pending.value:
        return approval

    approval.status = HumanApprovalStatus.rejected.value
    approval.approved_by = approved_by
    approval.approved_at = dt.datetime.now(dt.timezone.utc)
    approval.comment = comment
    await db.flush()
    return approval


async def get_pending_approvals(db: AsyncSession, user_id: uuid.UUID) -> list[HumanApproval]:
    """Item 2's own literal function -- item 2's own literal
    `(user_id)` signature: every real, still-pending request THIS user
    themselves requested (their own outstanding asks). See
    `list_pending_approvals_for_organization` below for the real,
    different, organization-wide view the approval ENDPOINTS actually
    need (any Admin approving someone else's request, not just their
    own)."""
    rows = (await db.scalars(
        select(HumanApproval).where(HumanApproval.requested_by == user_id, HumanApproval.status == HumanApprovalStatus.pending.value)
    )).all()
    return [await _resolve_if_expired(db, row) for row in rows]


async def list_pending_approvals_for_organization(db: AsyncSession, organization_id: uuid.UUID) -> list[HumanApproval]:
    """Real, additional function -- every real, still-pending request
    in this organization, regardless of who requested it (what an
    Admin reviewing a queue of approvals actually needs)."""
    rows = (await db.scalars(
        select(HumanApproval).where(HumanApproval.organization_id == organization_id, HumanApproval.status == HumanApprovalStatus.pending.value)
    )).all()
    resolved = [await _resolve_if_expired(db, row) for row in rows]
    return [row for row in resolved if row.status == HumanApprovalStatus.pending.value]


async def get_approval_status(db: AsyncSession, approval_id: uuid.UUID) -> str | None:
    """Item 2's own literal function -- `None` for an unknown id."""
    approval = await db.get(HumanApproval, approval_id)
    if approval is None:
        return None
    approval = await _resolve_if_expired(db, approval)
    return approval.status


async def check_approval_expired(db: AsyncSession, approval_id: uuid.UUID) -> bool:
    """Item 2's own literal function -- `True` if this request's real
    `expires_at` has passed (and, as a real side effect via
    `_resolve_if_expired`, a still-`pending` row is transitioned to
    `expired` right here). `False` for an unknown id -- "not expired"
    is honest when there's nothing to have expired."""
    approval = await db.get(HumanApproval, approval_id)
    if approval is None:
        return False
    approval = await _resolve_if_expired(db, approval)
    return approval.status == HumanApprovalStatus.expired.value
