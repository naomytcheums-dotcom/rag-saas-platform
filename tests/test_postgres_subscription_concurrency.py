"""R4: subscription transitions under real concurrency, on a DISPOSABLE PostgreSQL only (see tests/disposable_pg_guard.py: local host, marked
database name, explicit RAG_DISPOSABLE_PG_CONFIRM, not the application's DATABASE_URL; otherwise the module is skipped with the reason).

A writer (standing for a provider webhook) holds the subscription row lock without committing while the public service call of a
back-office change starts. Without a row lock the change would read the old period end and overwrite the writer's value (lost update);
with it, the change waits and builds on the committed value.
"""

import asyncio
import datetime as dt
import os
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.admin import Subscription
from api.models.organization import Organization
from api.services.admin_subscriptions import extend_subscription, get_or_create_subscription
from disposable_pg_guard import disposable_pg_refusal

URL = os.environ.get("RAG_DISPOSABLE_PG_URL", "")
_REFUSAL = disposable_pg_refusal(URL, os.environ.get("RAG_DISPOSABLE_PG_CONFIRM"), str(settings.DATABASE_URL), os.environ.get("DATABASE_URL"))

pytestmark = pytest.mark.skipif(_REFUSAL is not None, reason=f"PostgreSQL concurrency tests not authorized: {_REFUSAL}")


async def _world():
    engine = create_async_engine(URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    tag = uuid.uuid4().hex[:10]
    async with maker() as session:
        org = Organization(name=f"SubConc {tag}", slug=f"subconc-{tag}")
        session.add(org)
        await session.flush()
        sub = await get_or_create_subscription(session, org.id)
        await session.commit()
        ids = (org.id, sub.id)
    return engine, maker, ids


async def _cleanup(maker, ids):
    org_id, sub_id = ids
    async with maker() as session:
        for model, key in ((Subscription, sub_id), (Organization, org_id)):
            row = await session.get(model, key)
            if row is not None:
                await session.delete(row)
        await session.commit()


async def test_a_back_office_extension_builds_on_a_concurrent_writers_committed_value():
    engine, maker, ids = await _world()
    _org_id, sub_id = ids
    webhook_end = dt.datetime(2031, 1, 1, tzinfo=dt.timezone.utc)

    async def webhook_writer():
        async with maker() as session:
            sub = (await session.execute(select(Subscription).where(Subscription.id == sub_id).with_for_update())).scalar_one()
            sub.current_period_end = webhook_end
            await session.flush()
            await asyncio.sleep(0.6)  # the lock is held while the back-office call starts
            await session.commit()

    async def back_office_extension():
        await asyncio.sleep(0.2)
        async with maker() as session:
            await extend_subscription(session, sub_id, days=30)
            await session.commit()

    try:
        await asyncio.gather(webhook_writer(), back_office_extension())
        async with maker() as session:
            final = (await session.get(Subscription, sub_id)).current_period_end
        assert final == webhook_end + dt.timedelta(days=30), f"lost update: the extension ignored the committed period end ({final})"
    finally:
        await _cleanup(maker, ids)
        await engine.dispose()
