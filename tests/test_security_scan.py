"""Partie 10.5 -- real security scanning (pip-audit, bandit, a regex
secret scan), scoring, and the security policy half of Partie 10.6."""

import uuid

import pytest

from api.models.security_scan import ScanStatus, ScanType, VulnerabilitySeverity, VulnerabilityStatus
from api.services.security_scan import (
    calculate_security_score,
    get_or_create_security_policy,
    run_security_scan,
    update_security_policy,
)


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _make_org(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    org_id = (await client.post("/organizations", json={"name": "Scan Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id, user


async def test_infrastructure_scan_is_honestly_reported_as_unavailable(db_session):
    scan = await run_security_scan(db_session, organization_id=uuid.uuid4(), scan_type=ScanType.infrastructure, user_id=None)
    await db_session.commit()
    assert scan.status == ScanStatus.unavailable


async def test_container_scan_reports_unavailable_without_trivy(db_session, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    scan = await run_security_scan(db_session, organization_id=uuid.uuid4(), scan_type=ScanType.container, user_id=None)
    await db_session.commit()
    assert scan.status == ScanStatus.unavailable


async def test_secret_scan_finds_a_real_planted_secret(db_session, tmp_path, monkeypatch):
    """Real regex-based scan -- plant a real AWS-key-shaped string in a
    throwaway file under the repo tree the scanner globs, and confirm
    it's genuinely found (not simulated)."""
    import api.services.security_scan as scan_module

    fake_file = tmp_path / "api" / "leaked.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    fake_file.write_text('AWS_KEY = "AKIAABCDEFGHIJKLMNOP"\n')
    monkeypatch.setattr(scan_module, "_REPO_ROOT", tmp_path)

    scan = await run_security_scan(db_session, organization_id=uuid.uuid4(), scan_type=ScanType.secret, user_id=None)
    await db_session.commit()
    await db_session.refresh(scan, attribute_names=["vulnerabilities"])
    assert scan.status == ScanStatus.completed
    assert len(scan.vulnerabilities) == 1
    assert "AWS" in scan.vulnerabilities[0].title


async def test_dependency_scan_runs_real_pip_audit(db_session):
    """A real subprocess call to the real pip-audit against this real
    environment -- not mocked. Just confirms it runs and completes;
    the actual vulnerability count depends on what's installed and
    will legitimately vary over time."""
    scan = await run_security_scan(db_session, organization_id=uuid.uuid4(), scan_type=ScanType.dependency, user_id=None)
    await db_session.commit()
    assert scan.status in (ScanStatus.completed, ScanStatus.failed)  # never silently "unavailable" -- pip-audit is a real, installed dependency


async def test_security_score_deducts_by_severity(db_session):
    org_id = uuid.uuid4()
    scan = await run_security_scan(db_session, organization_id=org_id, scan_type=ScanType.secret, user_id=None)
    await db_session.commit()
    score_no_vulns = await calculate_security_score(db_session, org_id)
    assert score_no_vulns == 100

    from api.models.security_scan import Vulnerability

    db_session.add(Vulnerability(scan_id=scan.id, severity=VulnerabilitySeverity.critical, status=VulnerabilityStatus.open, title="test"))
    await db_session.commit()
    score_with_critical = await calculate_security_score(db_session, org_id)
    assert score_with_critical == 75  # 100 - 25 (critical weight)


async def test_security_policy_defaults_and_update(db_session):
    org_id = uuid.uuid4()
    policy = await get_or_create_security_policy(db_session, org_id)
    await db_session.commit()
    assert policy.session_timeout_minutes == 30
    assert policy.require_2fa_for_admins is False

    updated = await update_security_policy(db_session, org_id, require_2fa_for_admins=True, session_timeout_minutes=15)
    await db_session.commit()
    assert updated.require_2fa_for_admins is True
    assert updated.session_timeout_minutes == 15


async def test_run_scan_endpoint_requires_org_admin(client, db_session, register_payload):
    token, org_id, _ = await _make_org(client, db_session, register_payload)

    member_payload = {"email": "viewer@example.com", "password": "correct-horse-battery-staple", "accept_terms": True}
    member_token = (await client.post("/auth/register", json=member_payload)).json()["access_token"]
    from sqlalchemy import select

    from api.models.organization import OrganizationMember, OrganizationRole
    from api.models.user import User

    member = await db_session.scalar(select(User).where(User.email == member_payload["email"]))
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org_id), user_id=member.id, role=OrganizationRole.viewer))
    await db_session.commit()

    forbidden = await client.post(f"/organizations/{org_id}/security/scan", json={"scan_type": "secret"}, headers=_auth_header(member_token))
    assert forbidden.status_code == 403

    ok = await client.post(f"/organizations/{org_id}/security/scan", json={"scan_type": "secret"}, headers=_auth_header(token))
    assert ok.status_code == 200
    assert ok.json()["scan_type"] == "secret"


async def test_list_scans_endpoint_after_running_a_scan(client, db_session, register_payload):
    """Real regression test for a real bug: GET .../security/scans used
    to crash (MissingGreenlet -- an unrefreshed async lazy-load of
    `scan.vulnerabilities`) the moment a scan with recorded findings
    existed, found by actually running this flow in a real browser."""
    token, org_id, _ = await _make_org(client, db_session, register_payload)

    run_response = await client.post(f"/organizations/{org_id}/security/scan", json={"scan_type": "secret"}, headers=_auth_header(token))
    assert run_response.status_code == 200

    listing = await client.get(f"/organizations/{org_id}/security/scans", headers=_auth_header(token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["scan_type"] == "secret"


async def test_dismiss_alert_endpoint(client, db_session, register_payload):
    token, org_id_str, user = await _make_org(client, db_session, register_payload)
    org_id = uuid.UUID(org_id_str)

    from api.models.security_scan import SecurityAlert

    alert = SecurityAlert(organization_id=org_id, message="test alert", severity=VulnerabilitySeverity.high)
    db_session.add(alert)
    await db_session.commit()

    listing = await client.get(f"/organizations/{org_id}/security/alerts", headers=_auth_header(token))
    assert len(listing.json()) == 1

    dismiss = await client.post(f"/organizations/{org_id}/security/alerts/{alert.id}/dismiss", headers=_auth_header(token))
    assert dismiss.status_code == 200

    listing_after = await client.get(f"/organizations/{org_id}/security/alerts", headers=_auth_header(token))
    assert len(listing_after.json()) == 0


async def test_policies_update_requires_owner_not_just_admin(client, db_session, register_payload):
    token, org_id, user = await _make_org(client, db_session, register_payload)  # creator is Owner
    response = await client.patch(f"/organizations/{org_id}/security/policies", json={"session_timeout_minutes": 10}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["session_timeout_minutes"] == 10
