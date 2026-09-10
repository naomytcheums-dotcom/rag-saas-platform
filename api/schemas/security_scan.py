"""Request/response bodies for Partie 10.5 (security scanning) and the
SecurityPolicy half of Partie 10.6."""

import datetime as dt
import uuid

from pydantic import BaseModel

from api.models.security_scan import ScanStatus, ScanType, VulnerabilitySeverity, VulnerabilityStatus


class RunScanRequest(BaseModel):
    scan_type: ScanType


class VulnerabilityResponse(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    severity: VulnerabilitySeverity
    status: VulnerabilityStatus
    title: str
    description: str | None
    location: str | None
    cve_id: str | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class SecurityScanResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    scan_type: ScanType
    status: ScanStatus
    summary: str | None
    started_at: dt.datetime
    completed_at: dt.datetime | None
    vulnerability_count: int = 0

    model_config = {"from_attributes": True}


class VulnerabilityStatusUpdate(BaseModel):
    status: VulnerabilityStatus


class SecurityAlertResponse(BaseModel):
    id: uuid.UUID
    message: str
    severity: VulnerabilitySeverity
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class SecurityScoreResponse(BaseModel):
    score: int


class SecurityReportResponse(BaseModel):
    score: int
    open_vulnerabilities_by_severity: dict[str, int]
    total_open_vulnerabilities: int
    recent_scans: list[dict]


class SecurityPolicyResponse(BaseModel):
    require_2fa_for_admins: bool
    session_timeout_minutes: int
    max_login_attempts: int
    ip_allowlist: str | None
    min_password_strength_bits: int
    auto_lock_after_failed_attempts: bool
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


class SecurityPolicyUpdate(BaseModel):
    require_2fa_for_admins: bool | None = None
    session_timeout_minutes: int | None = None
    max_login_attempts: int | None = None
    ip_allowlist: str | None = None
    min_password_strength_bits: int | None = None
    auto_lock_after_failed_attempts: bool | None = None
