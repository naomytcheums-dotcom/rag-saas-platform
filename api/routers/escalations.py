"""Spec 15.1 -- human escalation tickets: list, filter, assign, change priority/status, resolve and annotate.

Every route is scoped to one organization and requires at least the manager role: an escalation is created by an agent run of that
organization (api/tools/human_escalation.py) and handled by its staff. A ticket of another organization answers 404, never 403."""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.audit_log import AuditAction
from api.models.escalation import Escalation, EscalationNote, EscalationStatus
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.escalations import (
    EscalationAssignRequest, EscalationListResponse, EscalationNoteCreateRequest, EscalationNoteResponse, EscalationResponse,
    EscalationStatsResponse, EscalationUpdateRequest,
)
from api.security.audit_log import log_audit_action
from api.security.organizations import require_org_manager
from api.tools.human_escalation import assign_escalation, update_escalation_status
from api.utils import MAX_PAGE_SIZE, client_ip

router = APIRouter(tags=["escalations"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
_FINAL = (EscalationStatus.resolved.value, EscalationStatus.closed.value)


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def _breached(row: Escalation, now: dt.datetime) -> bool:
    """A ticket breaches its SLA when it is still open past the deadline, or was closed after it."""
    if row.sla_due_at is None:
        return False
    if row.status in _FINAL:
        return _aware(row.resolved_at or now) > _aware(row.sla_due_at)
    return now > _aware(row.sla_due_at)


def _out(row: Escalation) -> EscalationResponse:
    out = EscalationResponse.model_validate(row)
    out.sla_breached = _breached(row, dt.datetime.now(dt.timezone.utc))
    return out


async def _get_in_org(db: AsyncSession, org_id: uuid.UUID, escalation_id: uuid.UUID) -> Escalation:
    row = await db.get(Escalation, escalation_id)
    if row is None or row.organization_id != org_id:
        raise _NOT_FOUND
    return row


@router.get("/organizations/{org_id}/escalations", response_model=EscalationListResponse)
async def list_escalations(
    org_id: uuid.UUID, status_filter: str | None = Query(default=None, alias="status"), priority: str | None = None,
    assignee_id: uuid.UUID | None = None, limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0),
    _caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    query = select(Escalation).where(Escalation.organization_id == org_id)
    if status_filter is not None:
        query = query.where(Escalation.status == status_filter)
    if priority is not None:
        query = query.where(Escalation.priority == priority)
    if assignee_id is not None:
        query = query.where(Escalation.assignee_id == assignee_id)
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (await db.scalars(query.order_by(Escalation.created_at.desc()).limit(limit).offset(offset))).all()
    return EscalationListResponse(items=[_out(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/organizations/{org_id}/escalations/stats", response_model=EscalationStatsResponse)
async def escalation_stats(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Escalation).where(Escalation.organization_id == org_id))).all()
    now = dt.datetime.now(dt.timezone.utc)
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_priority[r.priority] = by_priority.get(r.priority, 0) + 1
    return EscalationStatsResponse(total=len(rows), by_status=by_status, by_priority=by_priority, sla_breached=sum(1 for r in rows if _breached(r, now)))


@router.get("/organizations/{org_id}/escalations/{escalation_id}", response_model=EscalationResponse)
async def get_escalation(org_id: uuid.UUID, escalation_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    return _out(await _get_in_org(db, org_id, escalation_id))


@router.patch("/organizations/{org_id}/escalations/{escalation_id}", response_model=EscalationResponse)
async def update_escalation(
    org_id: uuid.UUID, escalation_id: uuid.UUID, payload: EscalationUpdateRequest, request: Request,
    caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    row = await _get_in_org(db, org_id, escalation_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") in _FINAL and not (data.get("resolution") or row.resolution):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A resolution text is required to resolve or close a ticket")
    if data.get("priority") is not None:
        row.priority = data["priority"]
    if data.get("status") is not None:
        await update_escalation_status(db, row.id, data["status"], data.get("resolution"))
    elif data.get("resolution") is not None:
        row.resolution = data["resolution"]
    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.ESCALATION_UPDATED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=org_id, resource_type="escalation", resource_id=str(row.id), metadata={k: v for k, v in data.items() if k != "resolution"},
    )
    await db.commit()
    await db.refresh(row)
    return _out(row)


@router.post("/organizations/{org_id}/escalations/{escalation_id}/assign", response_model=EscalationResponse)
async def assign(
    org_id: uuid.UUID, escalation_id: uuid.UUID, payload: EscalationAssignRequest, request: Request,
    caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    row = await _get_in_org(db, org_id, escalation_id)
    member = await db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == payload.assignee_id))
    if member is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The assignee must be a member of this organization")
    await assign_escalation(db, row.id, payload.assignee_id)
    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.ESCALATION_ASSIGNED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=org_id, resource_type="escalation", resource_id=str(row.id), metadata={"assignee_id": str(payload.assignee_id)},
    )
    await db.commit()
    await db.refresh(row)
    return _out(row)


@router.post("/organizations/{org_id}/escalations/{escalation_id}/notes", response_model=EscalationNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_note(
    org_id: uuid.UUID, escalation_id: uuid.UUID, payload: EscalationNoteCreateRequest,
    caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    row = await _get_in_org(db, org_id, escalation_id)
    note = EscalationNote(escalation_id=row.id, author_id=caller.user_id, body=payload.body)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@router.get("/organizations/{org_id}/escalations/{escalation_id}/notes", response_model=list[EscalationNoteResponse])
async def list_notes(org_id: uuid.UUID, escalation_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    row = await _get_in_org(db, org_id, escalation_id)
    return list((await db.scalars(select(EscalationNote).where(EscalationNote.escalation_id == row.id).order_by(EscalationNote.created_at))).all())
