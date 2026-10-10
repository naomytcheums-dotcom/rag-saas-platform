"""Spec 10.4.5 / 10.4.6 -- per-organization conversation retention."""

import datetime as dt
import uuid

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

import api.models  # noqa: F401 -- registers every table on Base.metadata
from api.database import Base
from api.models.conversation import Conversation, ConversationMessage
from api.models.organization import Organization
from api.models.organization_settings import OrganizationSettings
from api.models.user import User
from api.tasks.retention import purge_expired_conversations

NOW = dt.datetime(2026, 10, 10, 12, 0, tzinfo=dt.timezone.utc)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _record):  # so that ON DELETE CASCADE really runs, as on PostgreSQL
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _org(db, name, retention):
    owner = User(email=f"{name}@example.com", hashed_password="x")
    org = Organization(name=name, slug=f"{name}-{uuid.uuid4().hex[:6]}")
    db.add_all([owner, org])
    db.flush()
    db.add(OrganizationSettings(organization_id=org.id, settings={"conversation_retention_days": retention} if retention is not None else {}))
    db.flush()
    return org, owner


def _conv(db, org, owner, age_days):
    conv = Conversation(agent_id="a", user_id=owner.id, organization_id=org.id, title="t", updated_at=NOW - dt.timedelta(days=age_days))
    db.add(conv)
    db.flush()
    db.add(ConversationMessage(conversation_id=conv.id, role="user", content="hello"))
    db.flush()
    return conv.id


def test_only_conversations_older_than_the_policy_are_deleted(db):
    org, owner = _org(db, "keeper", 30)
    old, recent = _conv(db, org, owner, 45), _conv(db, org, owner, 5)
    removed = purge_expired_conversations(db, NOW)
    assert removed == {str(org.id): 1}
    remaining = set(db.scalars(select(Conversation.id)).all())
    assert remaining == {recent} and old not in remaining


def test_an_organization_without_a_policy_keeps_everything(db):
    org, owner = _org(db, "nopolicy", None)
    _conv(db, org, owner, 3000)
    assert purge_expired_conversations(db, NOW) == {}
    assert db.scalar(select(Conversation.id)) is not None


def test_a_policy_never_touches_another_organizations_conversations(db):
    strict, strict_owner = _org(db, "strict", 1)
    lenient, lenient_owner = _org(db, "lenient", None)
    _conv(db, strict, strict_owner, 10)
    keep = _conv(db, lenient, lenient_owner, 10)
    purge_expired_conversations(db, NOW)
    assert set(db.scalars(select(Conversation.id)).all()) == {keep}


@pytest.mark.parametrize("bad", [0, -5, True, "30", 1.5])
def test_invalid_policy_values_are_ignored(db, bad):
    org, owner = _org(db, f"bad{abs(hash(str(bad))) % 1000}", None)
    row = db.scalar(select(OrganizationSettings).where(OrganizationSettings.organization_id == org.id))
    row.settings = {"conversation_retention_days": bad}
    cid = _conv(db, org, owner, 4000)
    assert purge_expired_conversations(db, NOW) == {}
    assert db.get(Conversation, cid) is not None


def test_batches_limit_how_many_rows_one_run_removes(db):
    org, owner = _org(db, "batch", 1)
    for _ in range(5):
        _conv(db, org, owner, 20)
    assert purge_expired_conversations(db, NOW, batch_size=3) == {str(org.id): 3}
    assert purge_expired_conversations(db, NOW, batch_size=3) == {str(org.id): 2}


def test_messages_are_deleted_with_their_conversation(db):
    org, owner = _org(db, "cascade", 1)
    _conv(db, org, owner, 20)
    assert db.scalar(select(ConversationMessage.id)) is not None
    purge_expired_conversations(db, NOW)
    db.expire_all()
    assert db.scalar(select(ConversationMessage.id)) is None


async def test_the_retention_setting_is_stored_through_the_settings_endpoint(client, db_session):
    token = (await client.post("/auth/register", json={"email": "ret-owner@example.com", "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    org = (await client.post("/organizations", json={"name": "Ret Org"}, headers=h)).json()
    url = f"/organizations/{org['id']}/settings"
    assert (await client.get(url, headers=h)).json()["conversation_retention_days"] is None
    updated = await client.patch(url, json={"conversation_retention_days": 90}, headers=h)
    assert updated.status_code == 200 and updated.json()["conversation_retention_days"] == 90
    assert (await client.patch(url, json={"conversation_retention_days": 0}, headers=h)).status_code == 422
