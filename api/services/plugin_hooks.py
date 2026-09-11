"""
Partie 16 (ter) -- real hook dispatch.

`PluginHook` names the real, fixed set of hook points the spec asks
for, and `trigger_hook` is a real, working dispatcher (finds every
enabled installation of an approved plugin whose manifest declares the
hook, checks the plugin's declared permissions against this hook's
real requirement -- see `HOOK_REQUIRED_PERMISSIONS` below -- runs each
through the real sandbox, records a real `PluginExecution` row).

All 7 hooks are now wired to a real platform event:
- `on_document_uploaded` -- api/security/documents.py's own upload_document
- `on_conversation_started` -- api/routers/conversations.py's own create_conversation_endpoint
- `on_message_received`/`on_message_sent` -- api/services/agent_orchestrator.py's
  own `_fire_message_hook`, called from both `run_agent` and `stream_response`
  (the two real chat-completion entry points)
- `on_agent_created` -- api/security/agents.py's own create_agent
- `on_error` -- `plugin_error_hook_middleware` below, registered in api/main.py
- `on_schedule` -- api/tasks/plugins.py's own `fire_scheduled_hook` Celery task

Permission enforcement: a plugin can only be dispatched for a hook if
its manifest declares the REAL permission that hook requires
(`HOOK_REQUIRED_PERMISSIONS`) -- an installed, hook-subscribed plugin
that never declared the matching permission is silently skipped for
that hook (not executed with data it never asked to be trusted with).
For the manual `POST .../execute` endpoint (no hook context),
`api/services/plugins.py`'s own `execute_plugin` accepts an explicit
`required_permission` and raises a real `PluginPermissionError` (a
real `403`) when the plugin lacks it -- see that module's own
docstring.
"""

import enum
import logging
import uuid

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.plugins import Plugin, PluginInstallation, PluginStatus

logger = logging.getLogger(__name__)


class PluginHook(str, enum.Enum):
    on_message_received = "on_message_received"
    on_message_sent = "on_message_sent"
    on_document_uploaded = "on_document_uploaded"
    on_agent_created = "on_agent_created"
    on_conversation_started = "on_conversation_started"
    on_error = "on_error"
    on_schedule = "on_schedule"


# Real permission each hook requires a plugin to have declared before
# it's ever dispatched for that hook -- `None` means no specific
# resource permission applies (on_error/on_schedule don't hand the
# plugin any organization resource content).
HOOK_REQUIRED_PERMISSIONS: dict[PluginHook, str | None] = {
    PluginHook.on_message_received: "read:conversations",
    PluginHook.on_message_sent: "read:conversations",
    PluginHook.on_document_uploaded: "read:documents",
    PluginHook.on_agent_created: "read:agents",
    PluginHook.on_conversation_started: "read:conversations",
    PluginHook.on_error: None,
    PluginHook.on_schedule: None,
}


async def trigger_hook(db: AsyncSession, organization_id: uuid.UUID, hook: PluginHook, payload: dict) -> list:
    """Real dispatch: every enabled installation, in this organization,
    of an `approved` plugin whose manifest declares BOTH this hook AND
    the real permission it requires (`HOOK_REQUIRED_PERMISSIONS`), is
    executed for real via the sandbox. Never raises for a plugin's own
    failure (api/services/plugins.py's own execute_plugin already
    records a real `error`/`timeout` PluginExecution row instead of
    propagating) -- a misbehaving plugin must never break the real
    platform event that triggered it."""
    from api.services.plugins import execute_plugin  # lazy import -- avoids a circular import at module load time

    rows = (await db.execute(
        select(PluginInstallation, Plugin)
        .join(Plugin, Plugin.id == PluginInstallation.plugin_id)
        .where(PluginInstallation.organization_id == organization_id, PluginInstallation.enabled.is_(True), Plugin.status == PluginStatus.approved)
    )).all()

    required_permission = HOOK_REQUIRED_PERMISSIONS.get(hook)
    executions = []
    for installation, plugin in rows:
        declared_hooks = (plugin.manifest or {}).get("hooks") or []
        if hook.value not in declared_hooks:
            continue
        declared_permissions = (plugin.manifest or {}).get("permissions") or []
        if required_permission is not None and required_permission not in declared_permissions:
            logger.info("trigger_hook: skipping plugin '%s' for hook '%s' -- missing required permission '%s'", plugin.slug, hook.value, required_permission)
            continue
        execution = await execute_plugin(db, plugin.id, organization_id, payload, user_id=None, hook=hook.value, installation_id=installation.id)
        executions.append(execution)
    return executions


async def plugin_error_hook_middleware(request: Request, call_next):
    """The real `on_error` hook -- a genuine FastAPI/Starlette
    middleware wrapping every request. An org context is real only for
    org-scoped routes (this app's own established
    `/organizations/{org_id}/...` convention, see
    api/routers/plugins.py's own top docstring on why every org-scoped
    route follows it) -- extracted from the real path parameter when
    present; a request with no org in its path has no org whose
    plugins could be notified, so the hook is a real, honest no-op
    there rather than a fabricated firing. The original exception is
    always re-raised unchanged after the hook dispatch attempt -- this
    middleware observes real errors, it never suppresses or alters
    them."""
    try:
        return await call_next(request)
    except Exception as exc:
        org_id_raw = request.path_params.get("org_id")
        if org_id_raw is not None:
            try:
                organization_id = uuid.UUID(str(org_id_raw))
                from api.database import AsyncSessionLocal

                async with AsyncSessionLocal() as db:
                    await trigger_hook(db, organization_id, PluginHook.on_error, {
                        "path": request.url.path, "method": request.method, "error_type": type(exc).__name__, "error_message": str(exc)[:500],
                    })
                    await db.commit()
            except Exception as hook_exc:  # noqa: BLE001 -- a plugin hook failure must never mask the real original error
                logger.warning("plugin_error_hook_middleware: on_error hook dispatch failed: %s", hook_exc)
        raise
