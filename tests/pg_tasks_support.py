"""Shared helpers for the tests that run the Celery tasks against a real PostgreSQL (the disposable database of CI or of the local stack).

The tasks use the one shared synchronous engine (api/tasks/_sync_engine.py), bound to settings.DATABASE_URL. These tests skip themselves when that is not a reachable
PostgreSQL (the default fast suite runs on SQLite) and clean up what they create, so the shared database stays usable for the other tests.
"""

import uuid
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.config import settings
from api.models.organization import Organization


def require_postgres():
    if not settings.DATABASE_URL.startswith("postgresql"):
        pytest.skip("these tests need a PostgreSQL DATABASE_URL (disposable)")
    from api.tasks._sync_engine import sync_engine

    try:
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL is not reachable ({type(exc).__name__})")
    return sync_engine


@contextmanager
def organization(engine, label: str = "task"):
    """A throw-away organization; everything hanging on it is removed by the cascade (plus the named extra tables) when the block ends."""
    org_id = uuid.uuid4()
    with Session(engine) as db:
        db.add(Organization(id=org_id, name=f"{label} {org_id.hex[:6]}", slug=f"{label}-{org_id.hex[:12]}"))
        db.commit()
    try:
        yield org_id
    finally:
        with Session(engine) as db:
            db.execute(text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
            db.commit()


@contextmanager
def user(engine, label: str = "user"):
    """A throw-away user (removed when the block ends)."""
    from api.models.user import User

    user_id = uuid.uuid4()
    email = f"{label}-{user_id.hex[:10]}@example.test"
    with Session(engine) as db:
        db.add(User(id=user_id, email=email))
        db.commit()
    try:
        yield user_id, email
    finally:
        with Session(engine) as db:
            db.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})
            db.commit()


@contextmanager
def plan(engine, **fields):
    """A throw-away billing plan with a unique key (the catalogue plans are left untouched)."""
    from api.models.admin import Plan

    plan_id = uuid.uuid4()
    with Session(engine) as db:
        db.add(Plan(id=plan_id, key=f"t{plan_id.hex[:12]}", name="Task test plan", **fields))
        db.commit()
    try:
        yield plan_id
    finally:
        with Session(engine) as db:
            db.execute(text("DELETE FROM subscriptions WHERE plan_id = :p"), {"p": plan_id})
            db.execute(text("DELETE FROM plans WHERE id = :p"), {"p": plan_id})
            db.commit()
