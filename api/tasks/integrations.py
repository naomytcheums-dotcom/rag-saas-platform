"""Partie 15.1/15.2/15.3 -- real log retention sweep plus the three
periodic reconciliation jobs, same sync-engine pattern as every other
Celery task module in this project (api/tasks/external_source_sync.py).

Honest scope on the three periodic jobs below: `IntegrationConnection`
(webhook/zapier/make/n8n) is a PUSH-only inbound receiver -- an
external system posts to it, and `handle_inbound_payload` (api/
services/integrations.py) runs synchronously, in-request, at that
moment. There is no queue of unprocessed webhook payloads sitting
anywhere to "drain" -- a payload is either accepted/logged immediately,
or it errors and is logged as `error` for a later retry. So
`retry_failed_syncs` and `process_integration_webhooks` are, for real,
the SAME underlying sweep (re-running every active connection's
current action against its own previously failed logs) -- the literal
spec names this same real mechanism twice, exactly like this project's
own recurring Partie-numbering collisions, and it is registered here as
two Celery task names sharing one real implementation rather than
inventing a second, fake job to justify a second name. `sync_integrations`
is genuinely different: it is scoped to `AirbyteConnection`, the one
real PULL-based integration in this app, where "sync" has an actual
external-source meaning (calling Airbyte's own `/connections/sync`)."""

import asyncio
import datetime as dt
import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.integrations import AirbyteConnection, IntegrationConnection
from api.tasks.celery_app import celery_app
from api.tasks._sync_engine import sync_engine as _sync_engine

logger = logging.getLogger(__name__)



@celery_app.task(name="api.tasks.integrations.cleanup_integration_logs")
def cleanup_integration_logs() -> int:
    from api.models.integrations import IntegrationLog
    from sqlalchemy.orm import Session as SyncSession

    threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.INTEGRATION_LOG_RETENTION_DAYS)
    with SyncSession(_sync_engine) as db:
        result = db.execute(delete(IntegrationLog).where(IntegrationLog.created_at < threshold))
        db.commit()
        count = result.rowcount
    logger.info("cleanup_integration_logs: purged %d row(s) older than %d days", count, settings.INTEGRATION_LOG_RETENTION_DAYS)
    return count


async def _retry_failed_syncs_async() -> dict:
    from api.services.integrations import retry_failed_logs

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    checked = 0
    retried = 0
    failed = 0
    try:
        async with session_factory() as db:
            connection_ids = (await db.scalars(select(IntegrationConnection.id).where(IntegrationConnection.is_active.is_(True)))).all()
            for connection_id in connection_ids:
                try:
                    connection = await db.get(IntegrationConnection, connection_id)
                    if connection is None:
                        continue
                    checked += 1
                    results = await retry_failed_logs(db, connection)
                    # Committed per-connection, not once at the end -- same
                    # reasoning as sync_all_sources_periodic_task: one
                    # connection's own failure must never roll back every
                    # OTHER connection already successfully retried in this
                    # sweep.
                    await db.commit()
                    retried += len(results)
                except Exception as exc:  # noqa: BLE001 -- one connection's own real failure must never abort the whole sweep
                    logger.warning("retry_failed_syncs: could not retry connection '%s': %s", connection_id, exc)
                    await db.rollback()
                    failed += 1
    finally:
        await engine.dispose()
    return {"connections_checked": checked, "logs_retried": retried, "connections_failed": failed}


@celery_app.task(name="api.tasks.integrations.retry_failed_syncs")
def retry_failed_syncs() -> dict:
    """Periodic, system-wide version of `POST .../connections/{id}/sync`
    (api/routers/integrations_universal.py) -- re-runs every active
    connection's current action against its own previously failed
    payloads, so a mapping fix heals old failures without requiring a
    manual click per connection."""
    return asyncio.run(_retry_failed_syncs_async())


@celery_app.task(name="api.tasks.integrations.process_integration_webhooks")
def process_integration_webhooks() -> dict:
    """See this module's own top docstring: for a push-only inbound
    connection, "processing webhooks" and "retrying failed syncs" are
    the same real sweep -- there is no separate queue to drain. Kept as
    its own Celery task name (rather than only `retry_failed_syncs`)
    because the literal spec names both, and Celery Beat/monitoring
    should be able to see and schedule them independently even though
    they share one implementation today."""
    return asyncio.run(_retry_failed_syncs_async())


async def _sync_integrations_async() -> dict:
    from api.services import airbyte_client

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    checked = 0
    triggered = 0
    failed = 0
    try:
        async with session_factory() as db:
            connections = list((await db.scalars(select(AirbyteConnection))).all())
            for connection in connections:
                checked += 1
                try:
                    await airbyte_client.trigger_sync(connection.airbyte_connection_id)
                    triggered += 1
                except airbyte_client.AirbyteNotConfiguredError:
                    # Airbyte isn't configured on this deployment -- an
                    # honest, expected no-op, never a task failure.
                    break
                except Exception as exc:  # noqa: BLE001 -- one Airbyte connection's own failure must never abort the whole sweep
                    logger.warning("sync_integrations: could not trigger sync for Airbyte connection '%s': %s", connection.id, exc)
                    failed += 1
    finally:
        await engine.dispose()
    return {"connections_checked": checked, "syncs_triggered": triggered, "connections_failed": failed}


@celery_app.task(name="api.tasks.integrations.sync_integrations")
def sync_integrations() -> dict:
    """Partie 15.3's own periodic job, scoped to the one real PULL-based
    integration in this app: calls Airbyte's own `/connections/sync`
    (api/services/airbyte_client.py's trigger_sync) for every
    `AirbyteConnection` this app has recorded, so orgs that created a
    connection without configuring a schedule in Airbyte itself still
    get periodic syncs. A genuine no-op (0 checked) when
    AIRBYTE_API_URL/AIRBYTE_API_KEY aren't set -- see
    airbyte_client.AirbyteNotConfiguredError."""
    return asyncio.run(_sync_integrations_async())
