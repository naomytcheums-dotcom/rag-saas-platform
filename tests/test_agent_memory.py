"""Partie 5.1.11 -- short-term agent memory. Fast SQLite suite."""

import datetime as dt
import uuid

from api.services.agent_memory import (
    add_to_memory, clear_memory, create_session, get_all_memory, get_from_memory, update_memory,
)


async def test_create_session_creates_a_real_expiring_session(db_session):
    """Validation criterion: la création de session fonctionne."""
    session = await create_session(db_session, "agent-1", uuid.uuid4())
    await db_session.commit()

    assert session.agent_id == "agent-1"
    assert session.expires_at > dt.datetime.now(dt.timezone.utc)


async def test_add_and_get_from_memory(db_session):
    """Validation criterion: l'ajout en mémoire fonctionne, la
    récupération fonctionne."""
    session = await create_session(db_session, "agent-1")
    await add_to_memory(db_session, session.id, "user_name", "Ada")
    await db_session.commit()

    assert await get_from_memory(db_session, session.id, "user_name") == "Ada"


async def test_add_to_memory_upserts_an_existing_key(db_session):
    session = await create_session(db_session, "agent-1")
    await add_to_memory(db_session, session.id, "step", 1)
    await add_to_memory(db_session, session.id, "step", 2)
    await db_session.commit()

    assert await get_from_memory(db_session, session.id, "step") == 2


async def test_get_from_memory_returns_none_for_a_missing_key(db_session):
    session = await create_session(db_session, "agent-1")
    assert await get_from_memory(db_session, session.id, "never-set") is None


async def test_get_all_memory_returns_every_real_key(db_session):
    session = await create_session(db_session, "agent-1")
    await add_to_memory(db_session, session.id, "a", 1)
    await add_to_memory(db_session, session.id, "b", 2)
    await db_session.commit()

    assert await get_all_memory(db_session, session.id) == {"a": 1, "b": 2}


async def test_update_memory_changes_an_existing_key(db_session):
    """Validation criterion: la mise à jour fonctionne."""
    session = await create_session(db_session, "agent-1")
    await add_to_memory(db_session, session.id, "a", 1)
    await db_session.commit()

    updated = await update_memory(db_session, session.id, "a", 2)
    await db_session.commit()

    assert updated.value == 2
    assert await get_from_memory(db_session, session.id, "a") == 2


async def test_update_memory_is_a_real_no_op_for_a_missing_key(db_session):
    session = await create_session(db_session, "agent-1")
    assert await update_memory(db_session, session.id, "never-set", "x") is None


async def test_clear_memory_removes_every_real_item(db_session):
    session = await create_session(db_session, "agent-1")
    await add_to_memory(db_session, session.id, "a", 1)
    await add_to_memory(db_session, session.id, "b", 2)
    await db_session.commit()

    removed = await clear_memory(db_session, session.id)
    await db_session.commit()

    assert removed == 2
    assert await get_all_memory(db_session, session.id) == {}


# --------------------------------------- expiry --


async def test_get_from_memory_treats_a_real_expired_item_as_missing(db_session):
    """Validation criterion: l'expiration fonctionne."""
    session = await create_session(db_session, "agent-1")
    item = await add_to_memory(db_session, session.id, "a", 1)
    item.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    await db_session.commit()

    assert await get_from_memory(db_session, session.id, "a") is None


async def test_get_all_memory_excludes_a_real_expired_item(db_session):
    session = await create_session(db_session, "agent-1")
    fresh = await add_to_memory(db_session, session.id, "fresh", 1)
    stale = await add_to_memory(db_session, session.id, "stale", 2)
    stale.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    await db_session.commit()

    assert await get_all_memory(db_session, session.id) == {"fresh": 1}


# --------------------------------------- eviction when full --


async def test_add_to_memory_evicts_the_oldest_item_when_full(db_session, monkeypatch):
    """Validation criterion: robustesse -- que se passe-t-il si la
    mémoire est pleine."""
    from api.config import settings
    monkeypatch.setattr(settings, "AGENT_MEMORY_SIZE", 2)

    session = await create_session(db_session, "agent-1")
    await add_to_memory(db_session, session.id, "first", 1)
    await add_to_memory(db_session, session.id, "second", 2)
    await db_session.commit()
    await add_to_memory(db_session, session.id, "third", 3)
    await db_session.commit()

    memory = await get_all_memory(db_session, session.id)
    assert "first" not in memory
    assert memory == {"second": 2, "third": 3}


async def test_add_to_memory_disabled_is_a_real_no_op(db_session, monkeypatch):
    from api.config import settings
    monkeypatch.setattr(settings, "AGENT_MEMORY_ENABLED", False)

    session = await create_session(db_session, "agent-1")
    assert await add_to_memory(db_session, session.id, "a", 1) is None
