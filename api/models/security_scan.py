"""
Partie 10.5 -- security scanning. Real, locally-runnable scanners this
environment can actually execute (see api/services/security_scan.py's
own docstring for exactly which, and why the SaaS-only ones from the
literal spec -- Snyk/Trivy/SonarQube/FOSSA/OWASP ZAP as an on-demand
in-app scan -- are out of scope for an in-app "run a scan" button, as
opposed to the CI-level Snyk+ZAP job that already exists in
.github/workflows/regression.yml and stays unchanged by this module).
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class ScanType(str, enum.Enum):
    dependency = "dependency"  # pip-audit against every installed package
    code = "code"  # bandit SAST against api/
    secret = "secret"  # regex-based hardcoded-secret scan over the repo
    container = "container"  # real only if a local `trivy` binary is on PATH
    infrastructure = "infrastructure"  # not applicable -- no Terraform/CloudFormation in this repo


class ScanStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    unavailable = "unavailable"  # the real tool this scan type needs isn't installed/reachable here


class VulnerabilitySeverity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class VulnerabilityStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"
    false_positive = "false_positive"


class SecurityScan(Base):
    __tablename__ = "security_scans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    scan_type: Mapped[ScanType] = mapped_column(Enum(ScanType), nullable=False)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), nullable=False, default=ScanStatus.running)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    vulnerabilities: Mapped[list["Vulnerability"]] = relationship(back_populates="scan", cascade="all, delete-orphan")


class Vulnerability(Base):
    __tablename__ = "vulnerabilities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("security_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    severity: Mapped[VulnerabilitySeverity] = mapped_column(Enum(VulnerabilitySeverity), nullable=False)
    status: Mapped[VulnerabilityStatus] = mapped_column(Enum(VulnerabilityStatus), nullable=False, default=VulnerabilityStatus.open)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)  # file path, package name, etc.
    cve_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scan: Mapped["SecurityScan"] = relationship(back_populates="vulnerabilities")


class SecurityAlert(Base):
    __tablename__ = "security_alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    vulnerability_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vulnerabilities.id", ondelete="CASCADE"), nullable=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    severity: Mapped[VulnerabilitySeverity] = mapped_column(Enum(VulnerabilitySeverity), nullable=False)
    dismissed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SecurityPolicy(Base):
    """One row per organization -- the same "org-level override with a
    global default" shape as api/security/organization_settings.py's
    DEFAULT_SETTINGS, but as real mapped columns (a small, fixed set of
    real policy toggles) rather than a JSON blob, since every field here
    is independently meaningful to the Security screen (Partie 10.6)."""

    __tablename__ = "security_policies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    require_2fa_for_admins: Mapped[bool] = mapped_column(default=False, nullable=False)
    session_timeout_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    max_login_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    ip_allowlist: Mapped[str | None] = mapped_column(Text, nullable=True)  # newline-separated CIDR/IPs, empty/NULL = unrestricted
    min_password_strength_bits: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
    auto_lock_after_failed_attempts: Mapped[bool] = mapped_column(default=True, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
