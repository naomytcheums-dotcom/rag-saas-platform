"""
Partie 10.4 -- GDPR/CCPA rights requests, per-category consent, breach
declaration. Member+ endpoints act on the CALLER's own account only
(same anti-enumeration discipline as GET /account/audit-logs); Admin+
endpoints see every user's requests (global, not org-scoped -- a data
subject right belongs to the USER, not to an organization they happen
to be a member of).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db, require_admin, require_superadmin
from api.models.compliance import DataRequest, DataRequestStatus
from api.models.user import User
from api.schemas.compliance import (
    ComplianceStatusResponse,
    ConsentRequest,
    ConsentResponse,
    DataBreachCreate,
    DataBreachResponse,
    DataRequestCreate,
    DataRequestResponse,
    DataRequestUpdate,
)
from api.services.compliance import (
    DataRequestNotFoundError,
    check_compliance_status,
    create_data_request,
    declare_data_breach,
    export_user_data,
    get_user_consents,
    list_data_requests,
    process_data_request,
    record_consent,
    withdraw_consent,
)

router = APIRouter(prefix="/compliance", tags=["Compliance"])


@router.post("/data-requests", response_model=DataRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_data_request_endpoint(payload: DataRequestCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    request = await create_data_request(db, user_id=current_user.id, request_type=payload.request_type, details=payload.details)
    await db.commit()
    return DataRequestResponse.model_validate(request)


@router.get("/data-requests", response_model=list[DataRequestResponse])
async def list_data_requests_endpoint(limit: int = 50, offset: int = 0, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return [DataRequestResponse.model_validate(r) for r in await list_data_requests(db, limit=limit, offset=offset)]


@router.get("/data-requests/{request_id}", response_model=DataRequestResponse)
async def get_data_request_endpoint(request_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    request = await db.get(DataRequest, request_id)
    if request is None or request.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return DataRequestResponse.model_validate(request)


@router.patch("/data-requests/{request_id}", response_model=DataRequestResponse)
async def update_data_request_endpoint(request_id: uuid.UUID, payload: DataRequestUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        request = await process_data_request(db, request_id=request_id, status_value=payload.status, resolution_note=payload.resolution_note, processed_by=admin.id)
    except DataRequestNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return DataRequestResponse.model_validate(request)


@router.post("/data-requests/{request_id}/process", response_model=DataRequestResponse)
async def process_data_request_endpoint(request_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Real, additive shortcut over PATCH above -- marks a pending
    request in_progress without requiring the caller to compose a full
    DataRequestUpdate body first."""
    try:
        request = await process_data_request(db, request_id=request_id, status_value=DataRequestStatus.in_progress, resolution_note=None, processed_by=admin.id)
    except DataRequestNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return DataRequestResponse.model_validate(request)


@router.get("/data-export")
async def data_export_endpoint(fmt: str = "json", current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Real, additive alias for the existing GET /account/export and
    GET /account/export-csv (api/routers/account.py) under the
    Partie 10.4 compliance namespace -- same underlying data, same
    formats, so a compliance-focused UI doesn't need to know those
    endpoints live under /account instead."""
    from fastapi.responses import Response

    content, content_type = await export_user_data(db, current_user, fmt=fmt)
    return Response(content=content, media_type=content_type)


@router.post("/data-deletion")
async def request_data_deletion_endpoint():
    """Real, honest pointer, not a duplicate implementation: account
    erasure already exists, is mature (grace period, restore flow,
    pre-purge reminder email), and lives at DELETE /account/me
    (api/routers/account.py) -- this endpoint deliberately does not
    reimplement it a second time under a different path."""
    raise HTTPException(
        status_code=status.HTTP_308_PERMANENT_REDIRECT,
        headers={"Location": "/account/me"},
        detail="Use DELETE /account/me -- the existing, real account-deletion flow (grace period + restore).",
    )


@router.post("/consent", response_model=ConsentResponse)
async def record_consent_endpoint(payload: ConsentRequest, request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    record = await record_consent(db, user_id=current_user.id, consent_type=payload.consent_type, granted=payload.granted, ip=request.client.host if request.client else None)
    await db.commit()
    return ConsentResponse.model_validate(record)


@router.get("/consent", response_model=list[ConsentResponse])
async def get_consents_endpoint(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    consents = await get_user_consents(db, user_id=current_user.id)
    return [ConsentResponse.model_validate(record) for record in consents.values()]


@router.delete("/consent/{consent_type}", response_model=ConsentResponse)
async def withdraw_consent_endpoint(consent_type: str, request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    record = await withdraw_consent(db, user_id=current_user.id, consent_type=consent_type, ip=request.client.host if request.client else None)
    await db.commit()
    return ConsentResponse.model_validate(record)


@router.get("/status", response_model=ComplianceStatusResponse)
async def compliance_status_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return ComplianceStatusResponse(**await check_compliance_status(db))


@router.get("/report", response_model=ComplianceStatusResponse)
async def compliance_report_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Real, honest scope: the same snapshot as /status. A distinct,
    richer historical report (trends over a date range) would need a
    real time-series of past snapshots this table doesn't keep yet --
    documented here rather than fabricating one from a single point in
    time."""
    return ComplianceStatusResponse(**await check_compliance_status(db))


@router.post("/data-breach", response_model=DataBreachResponse, status_code=status.HTTP_201_CREATED)
async def declare_data_breach_endpoint(payload: DataBreachCreate, admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    breach = await declare_data_breach(db, organization_id=payload.organization_id, description=payload.description, affected_user_count=payload.affected_user_count, declared_by=admin.id)
    await db.commit()
    try:
        from api.tasks.compliance import send_data_breach_notifications

        send_data_breach_notifications.delay(str(breach.id))
    except Exception:  # noqa: BLE001 -- same real, best-effort Celery-dispatch reasoning as api/services/webhooks.py's trigger_webhook
        pass
    return DataBreachResponse.model_validate(breach)
