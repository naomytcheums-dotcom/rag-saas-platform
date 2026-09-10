"""
Partie 10.4 -- GDPR/CCPA rights-request tracking, per-category consent,
and breach declaration. Reuses the existing, mature machinery
(api/services/data_export.py, api/routers/account.py's DELETE
/account/me) for the two rights that already have a real, working
self-service flow (access/export, erasure/deletion) instead of
duplicating it -- this module's export_user_data() is a thin wrapper,
not a second implementation.
"""

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.compliance import ConsentRecord, DataBreach, DataRequest, DataRequestStatus, DataRequestType
from api.models.user import User
from api.services.data_export import build_account_export_data, render_account_export_csv


class ComplianceError(Exception):
    pass


class DataRequestNotFoundError(ComplianceError):
    pass


async def create_data_request(db: AsyncSession, *, user_id: uuid.UUID, request_type: DataRequestType, details: str | None) -> DataRequest:
    request = DataRequest(user_id=user_id, request_type=request_type, details=details)
    db.add(request)
    await db.flush()
    return request


async def list_data_requests(db: AsyncSession, *, user_id: uuid.UUID | None = None, limit: int = 50, offset: int = 0) -> list[DataRequest]:
    filters = [DataRequest.user_id == user_id] if user_id is not None else []
    return list((await db.scalars(
        select(DataRequest).where(*filters).order_by(DataRequest.created_at.desc()).limit(limit).offset(offset)
    )).all())


async def get_data_request_or_404(db: AsyncSession, request_id: uuid.UUID) -> DataRequest:
    request = await db.get(DataRequest, request_id)
    if request is None:
        raise DataRequestNotFoundError(str(request_id))
    return request


async def process_data_request(db: AsyncSession, *, request_id: uuid.UUID, status_value: DataRequestStatus, resolution_note: str | None, processed_by: uuid.UUID) -> DataRequest:
    request = await get_data_request_or_404(db, request_id)
    request.status = status_value
    request.resolution_note = resolution_note
    request.processed_by = processed_by
    if status_value in (DataRequestStatus.completed, DataRequestStatus.rejected):
        request.processed_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return request


async def export_user_data(db: AsyncSession, user: User, fmt: str = "json") -> tuple[str, str]:
    """Wraps the existing, already-mature api/services/data_export.py --
    returns (content, content_type). fmt="csv" reuses
    render_account_export_csv verbatim."""
    data = await build_account_export_data(db, user)
    if fmt == "csv":
        return render_account_export_csv(data), "text/csv"
    import json

    return json.dumps(data, default=str, indent=2), "application/json"


async def record_consent(db: AsyncSession, *, user_id: uuid.UUID, consent_type: str, granted: bool, ip: str | None) -> ConsentRecord:
    record = ConsentRecord(user_id=user_id, consent_type=consent_type, granted=granted, ip=ip)
    db.add(record)
    await db.flush()
    return record


async def get_user_consents(db: AsyncSession, *, user_id: uuid.UUID) -> dict[str, ConsentRecord]:
    """Latest row per consent_type -- the current, effective state (not
    the full history; GET /account/audit-logs-equivalent for compliance
    would be a separate "history" endpoint if ever needed)."""
    rows = (await db.scalars(
        select(ConsentRecord).where(ConsentRecord.user_id == user_id).order_by(ConsentRecord.created_at.desc())
    )).all()
    latest: dict[str, ConsentRecord] = {}
    for row in rows:
        latest.setdefault(row.consent_type, row)
    return latest


async def withdraw_consent(db: AsyncSession, *, user_id: uuid.UUID, consent_type: str, ip: str | None) -> ConsentRecord:
    return await record_consent(db, user_id=user_id, consent_type=consent_type, granted=False, ip=ip)


async def check_compliance_status(db: AsyncSession) -> dict:
    """A real, honest snapshot -- not a certification, just what this
    codebase can verify about itself: consent tracking exists, export/
    deletion exist and are wired, breach declaration exists."""
    pending_requests = await db.scalar(
        select(func.count()).select_from(DataRequest).where(DataRequest.status == DataRequestStatus.pending)
    ) or 0
    undeclared_breaches = await db.scalar(
        select(func.count()).select_from(DataBreach).where(DataBreach.notified_at.is_(None))
    ) or 0
    return {
        "gdpr_export_available": True,
        "gdpr_erasure_available": True,
        "gdpr_consent_tracking_available": True,
        "pending_data_requests": pending_requests,
        "unnotified_breaches": undeclared_breaches,
        "compliant": pending_requests == 0 and undeclared_breaches == 0,
    }


async def declare_data_breach(db: AsyncSession, *, organization_id: uuid.UUID | None, description: str, affected_user_count: int, declared_by: uuid.UUID) -> DataBreach:
    breach = DataBreach(organization_id=organization_id, description=description, affected_user_count=affected_user_count, declared_by=declared_by)
    db.add(breach)
    await db.flush()
    return breach
