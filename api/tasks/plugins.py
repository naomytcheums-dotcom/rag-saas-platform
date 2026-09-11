"""Partie 16 (ter) -- periodic plugin jobs. Same sync-engine pattern as
api/tasks/integrations.py's own cleanup_integration_logs -- these are
plain DB reads/writes plus calls into real, already-synchronous helpers
(api/security/plugin_manifest.py's scan_plugin_code,
api/services/plugins.py's download_plugin_code), so no async bridge is
needed here at all."""

import asyncio
import datetime as dt
import logging

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.plugins import Plugin, PluginExecution, PluginInstallation, PluginStatus
from api.security.plugin_manifest import PluginCodeSecurityError, scan_plugin_code
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), pool_pre_ping=True)


@celery_app.task(name="api.tasks.plugins.validate_pending_plugins")
def validate_pending_plugins() -> dict:
    """Real defense-in-depth: re-runs the SAME static code scan every
    pending plugin already passed at publish time. Only catches drift
    (a scan rule added/tightened after this plugin was submitted, but
    before an admin got to review it) -- a plugin that passed the scan
    at publish time and still passes it now is left untouched, real
    admin review still decides approve/reject either way."""
    from api.services.plugins import download_plugin_code

    checked = 0
    auto_rejected = 0
    with SyncSession(_sync_engine) as db:
        plugin_ids = db.scalars(select(Plugin.id).where(Plugin.status == PluginStatus.pending)).all()
        for plugin_id in plugin_ids:
            plugin = db.get(Plugin, plugin_id)
            if plugin is None:
                continue
            checked += 1
            try:
                code = download_plugin_code(plugin.code_key)
                scan_plugin_code(code)
            except PluginCodeSecurityError as exc:
                plugin.status = PluginStatus.rejected
                plugin.rejection_reason = f"Automated re-scan: {exc}"
                auto_rejected += 1
            except Exception as exc:  # noqa: BLE001 -- one plugin's storage hiccup must never abort the whole sweep
                logger.warning("validate_pending_plugins: could not re-scan plugin '%s': %s", plugin_id, exc)
                continue
            db.commit()
    logger.info("validate_pending_plugins: checked %d, auto-rejected %d", checked, auto_rejected)
    return {"checked": checked, "auto_rejected": auto_rejected}


@celery_app.task(name="api.tasks.plugins.scan_plugin_security")
def scan_plugin_security() -> dict:
    """Same real re-scan as validate_pending_plugins, applied to
    ALREADY-`approved` plugins -- if a scan rule is added/tightened
    after approval, this is what actually catches an already-live
    plugin, not just new submissions. Auto-`suspend`s (not `reject`,
    api/services/plugins.py's own suspend_plugin distinction) --
    existing installations are left in place, only new installs are
    blocked, same real reasoning as the manual suspend endpoint."""
    from api.services.plugins import download_plugin_code

    checked = 0
    auto_suspended = 0
    with SyncSession(_sync_engine) as db:
        plugin_ids = db.scalars(select(Plugin.id).where(Plugin.status == PluginStatus.approved)).all()
        for plugin_id in plugin_ids:
            plugin = db.get(Plugin, plugin_id)
            if plugin is None:
                continue
            checked += 1
            try:
                code = download_plugin_code(plugin.code_key)
                scan_plugin_code(code)
            except PluginCodeSecurityError as exc:
                plugin.status = PluginStatus.suspended
                plugin.rejection_reason = f"Automated security re-scan: {exc}"
                auto_suspended += 1
            except Exception as exc:  # noqa: BLE001 -- one plugin's storage hiccup must never abort the whole sweep
                logger.warning("scan_plugin_security: could not re-scan plugin '%s': %s", plugin_id, exc)
                continue
            db.commit()
    logger.info("scan_plugin_security: checked %d, auto-suspended %d", checked, auto_suspended)
    return {"checked": checked, "auto_suspended": auto_suspended}


@celery_app.task(name="api.tasks.plugins.cleanup_plugin_executions")
def cleanup_plugin_executions() -> int:
    threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.PLUGIN_EXECUTION_LOG_RETENTION_DAYS)
    with SyncSession(_sync_engine) as db:
        result = db.execute(delete(PluginExecution).where(PluginExecution.created_at < threshold))
        db.commit()
        count = result.rowcount
    logger.info("cleanup_plugin_executions: purged %d row(s) older than %d days", count, settings.PLUGIN_EXECUTION_LOG_RETENTION_DAYS)
    return count


@celery_app.task(name="api.tasks.plugins.update_plugin_stats")
def update_plugin_stats() -> int:
    """Real reconciliation sweep: install_plugin/uninstall_plugin
    already update `Plugin.install_count` directly for immediate
    accuracy (api/services/plugins.py) -- this recomputes it from a
    real COUNT(PluginInstallation) query and corrects any drift (e.g. a
    row deleted directly in the database, a crash between an
    installation write and its counter update), same direct-update-
    plus-periodic-reconciliation pattern this project already uses for
    billing usage."""
    updated = 0
    with SyncSession(_sync_engine) as db:
        rows = db.execute(
            select(Plugin.id, Plugin.install_count, func.count(PluginInstallation.id))
            .outerjoin(PluginInstallation, PluginInstallation.plugin_id == Plugin.id)
            .group_by(Plugin.id)
        ).all()
        for plugin_id, cached_count, real_count in rows:
            if cached_count != real_count:
                plugin = db.get(Plugin, plugin_id)
                plugin.install_count = real_count
                updated += 1
        db.commit()
    logger.info("update_plugin_stats: corrected install_count drift on %d plugin(s)", updated)
    return updated


async def _fire_scheduled_hook_async() -> dict:
    from api.models.organization import OrganizationMember
    from api.services.plugin_hooks import PluginHook, trigger_hook

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    checked_orgs = 0
    total_executions = 0
    try:
        async with session_factory() as db:
            # Real, honest scope: only organizations that actually have
            # at least one enabled installation of an approved plugin
            # declaring "on_schedule" -- not every organization on the
            # platform, most of which install no plugins at all.
            org_ids = (await db.scalars(
                select(PluginInstallation.organization_id)
                .join(Plugin, Plugin.id == PluginInstallation.plugin_id)
                .where(PluginInstallation.enabled.is_(True), Plugin.status == PluginStatus.approved)
                .distinct()
            )).all()
            for organization_id in org_ids:
                checked_orgs += 1
                try:
                    executions = await trigger_hook(db, organization_id, PluginHook.on_schedule, {
                        "fired_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    })
                    await db.commit()
                    total_executions += len(executions)
                except Exception as exc:  # noqa: BLE001 -- one organization's plugin failure must never abort the whole sweep
                    logger.warning("fire_scheduled_hook: on_schedule dispatch failed for org '%s': %s", organization_id, exc)
                    await db.rollback()
    finally:
        await engine.dispose()
    return {"organizations_checked": checked_orgs, "executions_fired": total_executions}


@celery_app.task(name="api.tasks.plugins.fire_scheduled_hook")
def fire_scheduled_hook() -> dict:
    """The real `on_schedule` hook -- a real Celery Beat periodic task
    (see api/tasks/celery_app.py's own beat_schedule entry,
    `fire-scheduled-plugin-hook-hourly`), the platform's own real
    equivalent of a cron trigger for plugins that declared interest in
    it."""
    return asyncio.run(_fire_scheduled_hook_async())
