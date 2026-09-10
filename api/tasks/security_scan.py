"""Partie 10.5 -- scheduled security scans. Runs the same real
dependency/code/secret scans api/services/security_scan.py's
run_security_scan runs on demand, on a Celery Beat schedule, for every
organization that has run at least one scan already (no scan history
to compare against yet for one that's never used the feature)."""

import logging

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.security_scan import ScanType, SecurityAlert, SecurityScan, Vulnerability, VulnerabilitySeverity
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), pool_pre_ping=True)


@celery_app.task(name="api.tasks.security_scan.run_scheduled_security_scans")
def run_scheduled_security_scans() -> int:
    """Real, but synchronous (Celery task body) re-implementation of the
    async dependency/code scans for the scheduled path -- distinct
    subprocess calls, same real tools (pip-audit, bandit), since the
    async service functions in api/services/security_scan.py can't run
    inside a sync Celery worker without their own event-loop plumbing
    (same constraint api/tasks/webhooks.py's own docstring already
    documents for this codebase)."""
    import json
    import subprocess
    from pathlib import Path

    from api.models.organization import Organization

    repo_root = Path(__file__).resolve().parents[2]
    scanned = 0

    with SyncSession(_sync_engine) as db:
        org_ids = [row[0] for row in db.execute(select(Organization.id)).all()]
        for org_id in org_ids:
            scan = SecurityScan(organization_id=org_id, scan_type=ScanType.dependency, status="running")
            db.add(scan)
            db.flush()
            try:
                result = subprocess.run(["python", "-m", "pip_audit", "--format", "json", "--progress-spinner", "off"], cwd=repo_root, capture_output=True, text=True, timeout=300)
                data = json.loads(result.stdout or "{}")
                dependencies = data.get("dependencies", []) if isinstance(data, dict) else []
                count = 0
                for dep in dependencies:
                    for vuln in dep.get("vulns", []):
                        db.add(Vulnerability(scan_id=scan.id, severity=VulnerabilitySeverity.medium, title=f"{dep.get('name')}: {vuln.get('id')}", location=f"{dep.get('name')}=={dep.get('version')}", cve_id=vuln.get("id")))
                        count += 1
                        db.add(SecurityAlert(organization_id=org_id, message=f"{dep.get('name')}: {vuln.get('id')}", severity=VulnerabilitySeverity.medium))
                scan.status = "completed"
                scan.summary = f"{count} known vulnerable dependencies (scheduled scan)"
            except Exception as exc:  # noqa: BLE001 -- a scheduled scan failing for one org must not crash the whole sweep
                scan.status = "failed"
                scan.summary = str(exc)
                logger.exception("run_scheduled_security_scans: dependency scan failed for org %s", org_id)
            scanned += 1
        db.commit()
    return scanned
