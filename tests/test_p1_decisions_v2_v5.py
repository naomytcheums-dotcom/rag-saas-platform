"""Decisions V2 to V5 of the billing/back-office review.

V2  the automatic credit refill leaves a ledger row (credit never appears out of nothing)
V3  only a superadmin lifts an organization's suspension (covered with the adapted test in test_admin_organizations.py)
V4  the audit-log purge never deletes the financial trail
V5  an organization's own audit view does not reveal which platform staff member acted on its account
"""

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import settings
from api.models.audit_log import AuditAction, AuditLog
from api.models.billing import Credit, CreditTransaction, CreditTransactionType
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User, UserRole
from api.security.audit_log import log_audit_action
from api.security.jwt import create_access_token


def _bearer(user_id) -> dict:
    token, _ = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


async def _user(db_session, email, role=UserRole.user):
    user = User(
        email=email, hashed_password="unused", is_email_verified=True, role=role,
        terms_version=settings.TERMS_VERSION, consent_given_at=dt.datetime.now(dt.timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _org_with_owner(db_session, owner):
    org = Organization(name="V Org", slug=f"v-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org.id, user_id=owner.id, role=OrganizationRole.owner))
    await db_session.commit()
    return org


async def _audit(db_session, user_id, org_id, resource_type, days_old):
    row = await log_audit_action(
        db_session, user_id=user_id, action=AuditAction.LOGIN_SUCCESS, ip=None, user_agent=None, success=True,
        organization_id=org_id, resource_type=resource_type,
    )
    row.timestamp = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_old)
    await db_session.commit()
    return row


# ------------------------------------------------------------------ V4


async def test_purge_keeps_the_financial_trail_and_removes_the_rest(client, db_session):
    superadmin = await _user(db_session, "purge-super@example.com", UserRole.superadmin)
    owner = await _user(db_session, "purge-owner@example.com")
    org = await _org_with_owner(db_session, owner)
    for rt in ("invoice", "subscription", "plan", "credits", "document", None):
        await _audit(db_session, owner.id, org.id, rt, 500)

    response = await client.delete("/audit/logs/purge?older_than_days=30", headers=_bearer(superadmin.id))
    assert response.status_code == 200

    remaining = set((await db_session.scalars(select(AuditLog.resource_type).where(AuditLog.action == AuditAction.LOGIN_SUCCESS.value))).all())
    assert remaining == {"invoice", "subscription", "plan", "credits"}


# ------------------------------------------------------------------ V5


async def test_the_organization_view_hides_which_platform_staff_member_acted(client, db_session):
    owner = await _user(db_session, "view-owner@example.com")
    staff = await _user(db_session, "view-staff@example.com", UserRole.superadmin)
    org = await _org_with_owner(db_session, owner)
    await _audit(db_session, owner.id, org.id, "document", 1)
    await _audit(db_session, staff.id, org.id, "subscription", 1)

    response = await client.get(f"/organizations/{org.id}/audit-logs?action=login_success", headers=_bearer(owner.id))
    assert response.status_code == 200
    actors = {item["user_id"] for item in response.json()["items"]}
    assert str(owner.id) in actors  # the organization still sees its own members' actions
    assert str(staff.id) not in actors  # ...but not the identity of platform staff
    assert None in actors and len(response.json()["items"]) == 2  # the row itself is still visible


async def test_the_platform_wide_audit_view_still_shows_every_actor(client, db_session):
    owner = await _user(db_session, "wide-owner@example.com")
    staff = await _user(db_session, "wide-staff@example.com", UserRole.superadmin)
    org = await _org_with_owner(db_session, owner)
    await _audit(db_session, staff.id, org.id, "subscription", 1)

    response = await client.get("/admin/audit-logs?action=login_success", headers=_bearer(staff.id))
    assert response.status_code == 200
    assert str(staff.id) in {item["user_id"] for item in response.json()["items"]}


# ------------------------------------------------------------------ V2


def test_the_automatic_refill_writes_a_ledger_row_and_is_off_by_default(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    import api.models  # noqa: F401 -- registers every table
    from api.database import Base
    from api.tasks import billing as billing_tasks

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        org = Organization(name="Refill Org", slug="refill-org")
        db.add(org)
        db.flush()
        db.add(Credit(organization_id=org.id, balance=1))
        db.commit()
        org_id = org.id
    monkeypatch.setattr(billing_tasks, "_sync_engine", engine)
    monkeypatch.setattr(settings, "CREDITS_REFILL_THRESHOLD", 10)
    monkeypatch.setattr(settings, "CREDITS_REFILL_AMOUNT", 50)

    monkeypatch.setattr(settings, "CREDITS_AUTO_REFILL", False)
    assert billing_tasks.auto_refill_credits() == 0  # off by default: nothing changes
    with Session(engine) as db:
        assert db.scalar(select(Credit.balance).where(Credit.organization_id == org_id)) == 1

    monkeypatch.setattr(settings, "CREDITS_AUTO_REFILL", True)
    assert billing_tasks.auto_refill_credits() == 1
    with Session(engine) as db:
        assert db.scalar(select(Credit.balance).where(Credit.organization_id == org_id)) == 51
        ledger = db.scalars(select(CreditTransaction).where(CreditTransaction.organization_id == org_id)).all()
        assert len(ledger) == 1
        assert ledger[0].type == CreditTransactionType.grant and ledger[0].amount == 50 and ledger[0].balance_after == 51
