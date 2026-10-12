"""Phase 3 of the 2026-10-12 security audit (TEN-004): routes that authorize the caller on the organization of the PATH and then act on an object named by
another identifier of the same path. The object must belong to that organization, otherwise an administrator of ANOTHER organization could act on it.

Covered: removal of a custom role assignment (RBAC), reading / updating a vulnerability and dismissing a security alert. Local SQLite fixtures only.
(The same defect on DELETE /organizations/{org_id}/api-keys/{key_id} is pinned in tests/test_p3_api_key_tenant_isolation.py.)
"""

from sqlalchemy import select

from api.models.rbac import UserCustomRole
from api.models.security_scan import ScanStatus, ScanType, SecurityAlert, SecurityScan, Vulnerability, VulnerabilitySeverity, VulnerabilityStatus
from test_document_idor import denied, make_tenants, snapshot


async def test_an_admin_of_another_organization_cannot_remove_a_role_assignment(client, db_session, monkeypatch):
    (owner, org_a, user_a), (attacker, org_b, _) = await make_tenants(client, db_session, monkeypatch, "rbacbind")
    created = await client.post(f"/organizations/{org_a}/rbac/roles", headers=owner, json={"name": "Support", "description": "private role"})
    assert created.status_code == 201, created.text
    role_id = created.json()["id"]
    assigned = await client.post(f"/organizations/{org_a}/rbac/users/{user_a}/roles", headers=owner, json={"role_id": role_id})
    assert assigned.status_code == 201, assigned.text

    async def assignment_exists() -> bool:
        db_session.expire_all()
        return await db_session.scalar(select(UserCustomRole).where(UserCustomRole.user_id == user_a)) is not None

    assert await assignment_exists()
    violations: list[str] = []
    await denied(client, "DELETE", f"/organizations/{org_b}/rbac/users/{user_a}/roles/{role_id}", attacker, violations)
    assert await assignment_exists(), "an administrator of another organization removed the role assignment of a user it does not manage"
    assert not violations, "\n".join(violations)

    # Control, last: the administrator of the owning organization can still remove it.
    own = await client.delete(f"/organizations/{org_a}/rbac/users/{user_a}/roles/{role_id}", headers=owner)
    assert own.status_code == 204, own.text
    assert not await assignment_exists()


async def test_an_admin_of_another_organization_cannot_read_or_change_a_vulnerability_or_dismiss_an_alert(client, db_session, monkeypatch):
    (owner, org_a, _), (attacker, org_b, _) = await make_tenants(client, db_session, monkeypatch, "scanbind")
    scan = SecurityScan(organization_id=org_a, scan_type=list(ScanType)[0], status=ScanStatus.completed)
    db_session.add(scan)
    await db_session.flush()
    vulnerability = Vulnerability(scan_id=scan.id, severity=VulnerabilitySeverity.low, title="private-vulnerability")
    db_session.add(vulnerability)
    await db_session.flush()
    alert = SecurityAlert(organization_id=org_a, vulnerability_id=vulnerability.id, message="private-alert", severity=VulnerabilitySeverity.low)
    db_session.add(alert)
    await db_session.commit()
    vulnerability_id, alert_id = vulnerability.id, alert.id
    other_status = next(s for s in VulnerabilityStatus if s != vulnerability.status)
    baseline = await snapshot(db_session, vulnerability, alert)

    control = await client.get(f"/organizations/{org_a}/security/vulnerabilities/{vulnerability_id}", headers=owner)
    assert control.status_code == 200, control.text

    violations: list[str] = []
    await denied(client, "GET", f"/organizations/{org_b}/security/vulnerabilities/{vulnerability_id}", attacker, violations)
    await denied(client, "PATCH", f"/organizations/{org_b}/security/vulnerabilities/{vulnerability_id}", attacker, violations, json={"status": other_status.value})
    await denied(client, "POST", f"/organizations/{org_b}/security/alerts/{alert_id}/dismiss", attacker, violations)
    db_session.expire_all()
    rows = [await db_session.get(Vulnerability, vulnerability_id), await db_session.get(SecurityAlert, alert_id)]
    assert await snapshot(db_session, *rows) == baseline, "a refused request must not change the vulnerability or the alert"
    assert not violations, "\n".join(violations)

    # Controls, last (they change the rows): the owning organization can still update and dismiss.
    updated = await client.patch(f"/organizations/{org_a}/security/vulnerabilities/{vulnerability_id}", headers=owner, json={"status": other_status.value})
    assert updated.status_code == 200, updated.text
    dismissed = await client.post(f"/organizations/{org_a}/security/alerts/{alert_id}/dismiss", headers=owner)
    assert dismissed.status_code == 200, dismissed.text
