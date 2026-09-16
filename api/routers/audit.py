"""
Audit findings 19/20 -- read access to the audit log
(api/models/audit_log.py, api/security/audit_log.py). Two tiers:
GET /account/audit-logs (any authenticated user, their own rows only) and
GET /admin/* (require_admin -- every user's rows, plus the failed-login
dashboard and an on-demand integrity check).
"""

import datetime as dt
import json
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db, require_admin, require_superadmin
from api.models.audit_log import AuditAction, AuditLog
from api.models.jwt_signing_key import JWTSigningKey
from api.models.user import User
from api.schemas.audit import (
    AuditActionEntry,
    AuditActionsResponse,
    AuditLogEntry,
    AuditLogIntegrityResponse,
    AuditLogListResponse,
    AuditStatsResponse,
    FailedLoginCount,
    FailedLoginStatsResponse,
    JWTSigningKeyEntry,
    JWTSigningKeyListResponse,
    PurgeResultResponse,
)
from api.security.audit_log import verify_audit_log_integrity
from api.utils import MAX_PAGE_SIZE
from api.security.organizations import require_org_admin as _require_org_admin_for_audit

router = APIRouter(tags=["audit"])



def _to_entry(row: AuditLog) -> AuditLogEntry:
    return AuditLogEntry(
        id=row.id, user_id=row.user_id, action=row.action, ip=row.ip, user_agent=row.user_agent,
        timestamp=row.timestamp, metadata=json.loads(row.metadata_json) if row.metadata_json else None,
        success=row.success, failure_reason=row.failure_reason,
    )


async def _list_audit_logs(
    db: AsyncSession, *, user_id: uuid.UUID | None, action: str | None, since: dt.datetime | None,
    until: dt.datetime | None, limit: int, offset: int, organization_id: uuid.UUID | None = None,
) -> AuditLogListResponse:
    filters = []
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if action is not None:
        filters.append(AuditLog.action == action)
    if since is not None:
        filters.append(AuditLog.timestamp >= since)
    if until is not None:
        filters.append(AuditLog.timestamp <= until)
    if organization_id is not None:
        filters.append(AuditLog.organization_id == organization_id)

    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    rows = (await db.scalars(
        select(AuditLog).where(*filters).order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
    )).all()
    return AuditLogListResponse(items=[_to_entry(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/account/audit-logs", response_model=AuditLogListResponse)
async def get_my_audit_logs(
    action: str | None = None,
    since: dt.datetime | None = None,
    until: dt.datetime | None = None,
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Audit finding 19: a user can see their own security-relevant history
    -- every login (successful or failed), password change, 2FA change,
    session revocation, etc. recorded for their account. Never another
    user's rows -- filtered by user_id unconditionally, not merely by
    default, so there's no query-parameter combination that widens it.
    """
    return await _list_audit_logs(db, user_id=current_user.id, action=action, since=since, until=until, limit=limit, offset=offset)


@router.get("/admin/audit-logs", response_model=AuditLogListResponse)
async def get_all_audit_logs(
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    since: dt.datetime | None = None,
    until: dt.datetime | None = None,
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Audit finding 19's optional admin half -- every account's rows,
    optionally narrowed to one user_id."""
    return await _list_audit_logs(db, user_id=user_id, action=action, since=since, until=until, limit=limit, offset=offset)


@router.get("/organizations/{org_id}/audit-logs", response_model=AuditLogListResponse)
async def get_organization_audit_logs(
    org_id: uuid.UUID, action: str | None = None, since: dt.datetime | None = None, until: dt.datetime | None = None,
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0),
    _caller=Depends(_require_org_admin_for_audit), db: AsyncSession = Depends(get_db),
):
    """Partie 10.2/10.6 -- an org-scoped view for the Security screen,
    gated by that ORGANIZATION's own Admin/Owner (require_org_admin) --
    deliberately NOT the same tier as GET /admin/audit-logs above
    (a global platform admin, unrelated to any one organization). Only
    rows carrying this org's organization_id (populated going forward
    by the specific actions this étape wired -- webhooks, documents,
    agents, conversations, integrations, widget, API keys) are visible
    here; older, pre-existing action types never populate that column
    and so never appear in this org-scoped view (see AuditLog's own
    docstring)."""
    return await _list_audit_logs(db, user_id=None, action=action, since=since, until=until, limit=limit, offset=offset, organization_id=org_id)


@router.get("/admin/failed-logins", response_model=FailedLoginStatsResponse)
async def get_failed_login_stats(
    window_minutes: int = Query(default=60, ge=1, le=10080),  # capped at 7 days
    top_n: int = Query(default=20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Audit finding 20: the dashboard a security team actually needs --
    which IPs and which targeted accounts are generating failed logins
    right now, not just a raw log to scroll through. Backed by the same
    AuditLog.action == LOGIN_FAILED rows api/services/security_alerts.py
    counts for real-time alerting, so this and the webhook/email alerts
    are always looking at the same underlying data.
    """
    window_start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=window_minutes)
    base_filter = (AuditLog.action == AuditAction.LOGIN_FAILED.value, AuditLog.timestamp >= window_start)

    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*base_filter)) or 0

    by_ip_rows = (await db.execute(
        select(AuditLog.ip, func.count().label("count")).where(*base_filter, AuditLog.ip.is_not(None))
        .group_by(AuditLog.ip).order_by(func.count().desc()).limit(top_n)
    )).all()

    # metadata_json is a JSON *string* column (portable across Postgres/
    # SQLite, see AuditLog's docstring) -- grouping by the email inside
    # it can't be done as a SQL GROUP BY the way `ip` above can, so it's
    # aggregated in Python instead. Fine at this scale: this endpoint
    # already caps its own window to 7 days and reads failed-login rows
    # only, never the full audit log.
    email_rows = (await db.scalars(select(AuditLog.metadata_json).where(*base_filter, AuditLog.metadata_json.is_not(None)))).all()
    email_counts: dict[str, int] = {}
    for raw in email_rows:
        email = json.loads(raw).get("email")
        if email:
            email_counts[email] = email_counts.get(email, 0) + 1
    top_emails = sorted(email_counts.items(), key=lambda pair: pair[1], reverse=True)[:top_n]

    return FailedLoginStatsResponse(
        window_minutes=window_minutes,
        total_failed_attempts=total,
        by_ip=[FailedLoginCount(key=ip, count=count) for ip, count in by_ip_rows],
        by_email=[FailedLoginCount(key=email, count=count) for email, count in top_emails],
    )


@router.get("/admin/audit-logs/verify-integrity", response_model=AuditLogIntegrityResponse)
async def verify_audit_logs_integrity(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """
    Audit finding 18's tamper-evidence, made checkable on demand rather
    than a guarantee nobody ever actually verifies. Walks the entire
    hash chain -- see api/security/audit_log.py's verify_audit_log_integrity
    for what "intact" actually means here.
    """
    intact, first_tampered_id = await verify_audit_log_integrity(db)
    return AuditLogIntegrityResponse(intact=intact, first_tampered_entry_id=first_tampered_id)


@router.get("/audit/stats", response_model=AuditStatsResponse)
async def get_audit_stats_endpoint(
    since: dt.datetime | None = None, until: dt.datetime | None = None,
    _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    """Partie 10.2 -- a real aggregate over the same rows GET
    /admin/audit-logs paginates through, so a dashboard can show
    "1,204 events, 12 failed" without fetching every page itself."""
    filters = []
    if since is not None:
        filters.append(AuditLog.timestamp >= since)
    if until is not None:
        filters.append(AuditLog.timestamp <= until)

    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    successful = await db.scalar(select(func.count()).select_from(AuditLog).where(*filters, AuditLog.success.is_(True))) or 0
    by_action_rows = (await db.execute(
        select(AuditLog.action, func.count()).where(*filters).group_by(AuditLog.action)
    )).all()
    return AuditStatsResponse(
        total=total, successful=successful, failed=total - successful,
        by_action={action: count for action, count in by_action_rows},
    )


@router.get("/audit/actions", response_model=AuditActionsResponse)
async def get_audit_actions_endpoint(_admin: User = Depends(require_admin)):
    """Partie 10.2 -- the full, real, fixed list of action types this
    codebase's log_audit_action() can ever write (api/models/audit_log.py's
    AuditAction enum), not a distinct list maintained by hand."""
    return AuditActionsResponse(items=[AuditActionEntry(key=action.value) for action in AuditAction])


@router.get("/audit/export")
async def export_audit_logs_endpoint(
    fmt: str = Query(default="json", pattern="^(json|csv)$"),
    user_id: uuid.UUID | None = None, action: str | None = None,
    since: dt.datetime | None = None, until: dt.datetime | None = None,
    _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    """Partie 10.2 -- exports every matching row (up to a real, fixed
    10,000-row safety cap -- a genuine export, not a paginated listing
    reused as-is) as real JSON or CSV."""
    from fastapi.responses import Response

    listing = await _list_audit_logs(db, user_id=user_id, action=action, since=since, until=until, limit=10000, offset=0)
    if fmt == "csv":
        import csv
        import io

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["id", "user_id", "action", "ip", "user_agent", "timestamp", "success", "failure_reason"])
        for entry in listing.items:
            writer.writerow([entry.id, entry.user_id, entry.action, entry.ip, entry.user_agent, entry.timestamp.isoformat(), entry.success, entry.failure_reason])
        return Response(content=buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit-logs.csv"})

    return Response(content=json.dumps([entry.model_dump(mode="json") for entry in listing.items]), media_type="application/json")


@router.get("/audit/user/{user_id}", response_model=AuditLogListResponse)
async def get_user_audit_logs_endpoint(
    user_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    return await _list_audit_logs(db, user_id=user_id, action=None, since=None, until=None, limit=limit, offset=offset)


@router.get("/audit/resource/{resource_type}/{resource_id}", response_model=AuditLogListResponse)
async def get_resource_audit_logs_endpoint(
    resource_type: str, resource_id: str, limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    """Partie 10.2 -- only finds rows logged AFTER the resource_type/
    resource_id columns were added (see AuditLog's own docstring);
    older rows for the same resource, if any, are still visible via
    GET /admin/audit-logs?action=... using metadata_json instead."""
    filters = [AuditLog.resource_type == resource_type, AuditLog.resource_id == resource_id]
    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    rows = (await db.scalars(
        select(AuditLog).where(*filters).order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
    )).all()
    return AuditLogListResponse(items=[_to_entry(r) for r in rows], total=total, limit=limit, offset=offset)


@router.delete("/audit/logs/purge", response_model=PurgeResultResponse)
async def purge_audit_logs_endpoint(
    older_than_days: int = Query(ge=1), _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db),
):
    """Partie 10.2 -- superadmin-only (platform-wide, irreversible,
    same tier as PATCH /admin/users/{id}/role): deletes every row older
    than `older_than_days`. Breaks the real hash chain for every row
    still remaining after the purge point -- by design (a purge is a
    deliberate, explicit exception to "the log is append-only", not
    something that silently happens); GET /admin/audit-logs/verify-integrity
    will correctly report the chain as broken starting at the oldest
    surviving row after this runs, which is the honest, expected result
    of a real purge, not a bug to hide."""
    threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=older_than_days)
    rows = (await db.scalars(select(AuditLog).where(AuditLog.timestamp < threshold))).all()
    count = len(rows)
    for row in rows:
        await db.delete(row)
    await db.commit()
    return PurgeResultResponse(deleted=count)


@router.get("/admin/jwt-keys", response_model=JWTSigningKeyListResponse)
async def list_jwt_signing_keys(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """
    Audit finding 28's "notification administrateur" requirement, made
    checkable on demand rather than relying solely on the one-shot email
    api/tasks/jwt_key_rotation.py sends at the moment of a rotation --
    lets an operator confirm rotation is actually happening on schedule
    (or debug why it isn't) at any time. The secret itself is never
    returned, only rotation metadata (see JWTSigningKeyEntry's docstring).
    """
    rows = (await db.scalars(select(JWTSigningKey).order_by(JWTSigningKey.created_at.desc()))).all()
    return JWTSigningKeyListResponse(items=[JWTSigningKeyEntry.model_validate(row) for row in rows])
