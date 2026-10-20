"""Celery tasks of api/tasks/sales.py against a real PostgreSQL: partner commissions (calculation, payout threshold), license expiry, usage-limit warnings."""

import datetime as dt
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import settings
from api.models.admin import Subscription, SubscriptionStatus
from api.models.billing import UsageAlert
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.sales import License, LicenseStatus, PartnerCommission, PartnerCommissionStatus, Reseller, SubClient
from api.tasks.sales import calculate_partner_commissions, check_usage_limits, pay_partner_commissions, validate_licenses
from pg_tasks_support import organization, plan, require_postgres, user

NOW = dt.datetime.now(dt.timezone.utc)


@pytest.fixture
def engine():
    return require_postgres()


def _last_month() -> tuple[dt.date, dt.date]:
    end = dt.date.today().replace(day=1) - dt.timedelta(days=1)
    return end.replace(day=1), end


def test_a_reseller_gets_one_commission_row_per_month_from_its_active_sub_clients(engine):
    start, end = _last_month()
    with organization(engine, "reseller") as reseller_org, organization(engine, "client") as client_org, organization(engine, "lonely") as lonely_org, plan(engine, monthly_price_cents=5000) as plan_id:
        with Session(engine) as db:
            reseller, lonely = Reseller(organization_id=reseller_org, commission_percent=20), Reseller(organization_id=lonely_org, commission_percent=30)
            db.add_all([reseller, lonely])
            db.flush()
            db.add(SubClient(reseller_id=reseller.id, organization_id=client_org))
            db.add(Subscription(organization_id=client_org, plan_id=plan_id, status=SubscriptionStatus.active))
            db.commit()
            reseller_id, lonely_id = reseller.id, lonely.id

        assert calculate_partner_commissions() >= 1
        calculate_partner_commissions()  # idempotent: the same period is not written twice

        with Session(engine) as db:
            rows = db.scalars(select(PartnerCommission).where(PartnerCommission.reseller_id == reseller_id)).all()
            assert [(r.period_start, r.period_end, r.amount_cents, r.status) for r in rows] == [(start, end, 1000, PartnerCommissionStatus.pending)]  # 20 % of 5000
            assert db.scalars(select(PartnerCommission).where(PartnerCommission.reseller_id == lonely_id)).all() == []  # no sub-client, nothing to pay


def test_a_free_sub_client_earns_no_commission(engine):
    with organization(engine, "reseller") as reseller_org, organization(engine, "client") as client_org, plan(engine, monthly_price_cents=0) as plan_id:
        with Session(engine) as db:
            reseller = Reseller(organization_id=reseller_org, commission_percent=50)
            db.add(reseller)
            db.flush()
            db.add(SubClient(reseller_id=reseller.id, organization_id=client_org))
            db.add(Subscription(organization_id=client_org, plan_id=plan_id, status=SubscriptionStatus.active))
            db.commit()
            reseller_id = reseller.id

        calculate_partner_commissions()

        with Session(engine) as db:
            assert db.scalars(select(PartnerCommission).where(PartnerCommission.reseller_id == reseller_id)).all() == []


def test_commissions_are_paid_out_only_once_a_reseller_reaches_the_minimum(engine, monkeypatch):
    monkeypatch.setattr(settings, "PARTNER_MIN_PAYOUT_CENTS", 5000)
    start, end = _last_month()
    with organization(engine, "rich") as rich_org, organization(engine, "poor") as poor_org:
        with Session(engine) as db:
            rich, poor = Reseller(organization_id=rich_org), Reseller(organization_id=poor_org)
            db.add_all([rich, poor])
            db.flush()
            db.add_all([
                PartnerCommission(reseller_id=rich.id, period_start=start, period_end=end, amount_cents=3000),
                PartnerCommission(reseller_id=rich.id, period_start=start - dt.timedelta(days=31), period_end=start - dt.timedelta(days=1), amount_cents=3000),
                PartnerCommission(reseller_id=poor.id, period_start=start, period_end=end, amount_cents=1000),
            ])
            db.commit()
            rich_id, poor_id = rich.id, poor.id

        assert pay_partner_commissions() >= 1

        with Session(engine) as db:
            rich_rows = db.scalars(select(PartnerCommission).where(PartnerCommission.reseller_id == rich_id)).all()
            poor_rows = db.scalars(select(PartnerCommission).where(PartnerCommission.reseller_id == poor_id)).all()
            assert all(r.status == PartnerCommissionStatus.paid and r.paid_at is not None for r in rich_rows) and len(rich_rows) == 2
            assert all(r.status == PartnerCommissionStatus.pending and r.paid_at is None for r in poor_rows)


def test_licenses_past_their_expiry_are_flipped_to_expired(engine):
    with Session(engine) as db:
        overdue = License(key=f"L-{uuid.uuid4().hex}", plan_key="pro", expires_at=NOW - dt.timedelta(days=1))
        valid = License(key=f"L-{uuid.uuid4().hex}", plan_key="pro", expires_at=NOW + dt.timedelta(days=30))
        perpetual = License(key=f"L-{uuid.uuid4().hex}", plan_key="pro")
        db.add_all([overdue, valid, perpetual])
        db.commit()
        ids = [overdue.id, valid.id, perpetual.id]
    try:
        assert validate_licenses() >= 1
        with Session(engine) as db:
            overdue_row, valid_row, perpetual_row = (db.get(License, i) for i in ids)
            assert overdue_row.status == LicenseStatus.expired
            assert valid_row.status == LicenseStatus.active and perpetual_row.status == LicenseStatus.active
    finally:
        with Session(engine) as db:
            for license_id in ids:
                db.delete(db.get(License, license_id))
            db.commit()


def _org_at_its_member_limit(engine, db, org_id, plan_id, owner_id, threshold=80):
    db.add(Subscription(organization_id=org_id, plan_id=plan_id, status=SubscriptionStatus.active))
    db.add(OrganizationMember(organization_id=org_id, user_id=owner_id, role=OrganizationRole.owner))
    db.add(UsageAlert(organization_id=org_id, resource_type="members", threshold_percent=threshold))
    db.commit()


def test_the_owner_is_warned_when_a_resource_crosses_the_alert_threshold(engine, monkeypatch):
    sent = []
    monkeypatch.setattr("api.services.email_branding.send_branded_usage_limit_warning_email_sync", lambda db, org_id, email, resource, percent, limit: sent.append((org_id, email, resource, percent, limit)))
    with organization(engine, "usage") as org_id, user(engine, "owner") as (owner_id, owner_email), plan(engine, max_members=1) as plan_id:
        with Session(engine) as db:
            _org_at_its_member_limit(engine, db, org_id, plan_id, owner_id)

        assert check_usage_limits() >= 1

        assert (org_id, owner_email, "members", 100, 1) in sent


def test_no_warning_below_the_threshold_without_a_limit_and_a_failing_mailer_does_not_stop_the_sweep(engine, monkeypatch):
    sent = []
    monkeypatch.setattr("api.services.email_branding.send_branded_usage_limit_warning_email_sync", lambda *args: sent.append(args))
    with organization(engine, "below") as below_org, organization(engine, "unlimited") as unlimited_org, user(engine, "o1") as (owner1, _e1), user(engine, "o2") as (owner2, _e2), plan(engine, max_members=10) as small_plan, plan(engine) as no_limit_plan:
        with Session(engine) as db:
            _org_at_its_member_limit(engine, db, below_org, small_plan, owner1)  # 1 of 10 members = 10 %
            _org_at_its_member_limit(engine, db, unlimited_org, no_limit_plan, owner2)  # no limit configured

        check_usage_limits()

        assert not [s for s in sent if s[1] in (below_org, unlimited_org)]

        def boom(*args):
            raise RuntimeError("mail provider down")

        monkeypatch.setattr("api.services.email_branding.send_branded_usage_limit_warning_email_sync", boom)
        assert check_usage_limits() >= 0  # the sweep ends normally
