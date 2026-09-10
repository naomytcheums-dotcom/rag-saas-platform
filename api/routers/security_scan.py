"""Partie 10.5 -- security scanning, org-scoped under
`/organizations/{org_id}/security/...` (same real convention as
api/routers/rbac.py -- see that module's own docstring)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.models.security_scan import VulnerabilityStatus
from api.models.user import User
from api.schemas.security_scan import (
    RunScanRequest,
    SecurityAlertResponse,
    SecurityPolicyResponse,
    SecurityPolicyUpdate,
    SecurityReportResponse,
    SecurityScanResponse,
    SecurityScoreResponse,
    VulnerabilityResponse,
    VulnerabilityStatusUpdate,
)
from api.security.organizations import require_org_admin, require_org_owner
from api.services.security_scan import (
    calculate_security_score,
    dismiss_alert,
    generate_security_report,
    get_or_create_security_policy,
    get_security_alerts,
    get_security_scan,
    get_vulnerability,
    list_security_scans,
    list_vulnerabilities,
    run_security_scan,
    update_security_policy,
    update_vulnerability_status,
)

router = APIRouter(tags=["Security scanning"])


def _scan_to_response(scan) -> SecurityScanResponse:
    return SecurityScanResponse(
        id=scan.id, organization_id=scan.organization_id, scan_type=scan.scan_type, status=scan.status,
        summary=scan.summary, started_at=scan.started_at, completed_at=scan.completed_at,
        vulnerability_count=len(scan.vulnerabilities) if scan.vulnerabilities is not None else 0,
    )


@router.post("/organizations/{org_id}/security/scan", response_model=SecurityScanResponse)
async def run_scan_endpoint(org_id: uuid.UUID, payload: RunScanRequest, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    scan = await run_security_scan(db, organization_id=org_id, scan_type=payload.scan_type, user_id=caller.user_id)
    await db.commit()
    await db.refresh(scan, attribute_names=["vulnerabilities"])
    return _scan_to_response(scan)


@router.get("/organizations/{org_id}/security/scans", response_model=list[SecurityScanResponse])
async def list_scans_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    scans = await list_security_scans(db, org_id)
    return [_scan_to_response(s) for s in scans]


@router.get("/organizations/{org_id}/security/scans/{scan_id}", response_model=SecurityScanResponse)
async def get_scan_endpoint(org_id: uuid.UUID, scan_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    scan = await get_security_scan(db, scan_id)
    if scan is None or scan.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return _scan_to_response(scan)


@router.get("/organizations/{org_id}/security/vulnerabilities", response_model=list[VulnerabilityResponse])
async def list_vulnerabilities_endpoint(org_id: uuid.UUID, status_filter: VulnerabilityStatus | None = None, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    return [VulnerabilityResponse.model_validate(v) for v in await list_vulnerabilities(db, org_id, status_filter)]


@router.get("/organizations/{org_id}/security/vulnerabilities/{vuln_id}", response_model=VulnerabilityResponse)
async def get_vulnerability_endpoint(org_id: uuid.UUID, vuln_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    vuln = await get_vulnerability(db, vuln_id)
    if vuln is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return VulnerabilityResponse.model_validate(vuln)


@router.patch("/organizations/{org_id}/security/vulnerabilities/{vuln_id}", response_model=VulnerabilityResponse)
async def update_vulnerability_endpoint(org_id: uuid.UUID, vuln_id: uuid.UUID, payload: VulnerabilityStatusUpdate, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    vuln = await update_vulnerability_status(db, vuln_id, payload.status)
    if vuln is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return VulnerabilityResponse.model_validate(vuln)


@router.get("/organizations/{org_id}/security/alerts", response_model=list[SecurityAlertResponse])
async def list_alerts_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    return [SecurityAlertResponse.model_validate(a) for a in await get_security_alerts(db, org_id)]


@router.post("/organizations/{org_id}/security/alerts/{alert_id}/dismiss", response_model=SecurityAlertResponse)
async def dismiss_alert_endpoint(org_id: uuid.UUID, alert_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    alert = await dismiss_alert(db, alert_id, caller.user_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return SecurityAlertResponse.model_validate(alert)


@router.get("/organizations/{org_id}/security/score", response_model=SecurityScoreResponse)
async def get_score_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    return SecurityScoreResponse(score=await calculate_security_score(db, org_id))


@router.get("/organizations/{org_id}/security/report", response_model=SecurityReportResponse)
async def get_report_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    return SecurityReportResponse(**await generate_security_report(db, org_id))


@router.get("/organizations/{org_id}/security/policies", response_model=SecurityPolicyResponse)
async def get_policies_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    policy = await get_or_create_security_policy(db, org_id)
    await db.commit()
    await db.refresh(policy)  # server_default/onupdate columns (updated_at) need a real refresh after commit expires them
    return SecurityPolicyResponse.model_validate(policy)


@router.patch("/organizations/{org_id}/security/policies", response_model=SecurityPolicyResponse)
async def update_policies_endpoint(org_id: uuid.UUID, payload: SecurityPolicyUpdate, _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db)):
    policy = await update_security_policy(db, org_id, **payload.model_dump())
    await db.commit()
    await db.refresh(policy)
    return SecurityPolicyResponse.model_validate(policy)
