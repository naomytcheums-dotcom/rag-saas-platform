"""
Partie 16 (ter) -- real hook dispatch.

Honest scope: `PluginHook` names the real, fixed set of hook points the
spec asks for, and `trigger_hook` is a real, working dispatcher
(finds every enabled installation of an approved plugin whose manifest
declares the hook, runs each through the real sandbox, records a real
`PluginExecution` row). ONE real platform call site is actually wired
to fire it -- `on_document_uploaded`, from
api/security/documents.py's own upload_document -- to prove the whole
mechanism genuinely works end-to-end rather than existing only as
dead code. The other 6 hooks are real and dispatchable (any test or
future call site can call `trigger_hook` today and it will work), but
wiring each into its own existing business-logic module
(conversations.py, agents.py, the message-send path, the platform
error handler, a scheduler) is real, separate integration work left
for a follow-up -- see docs/marketplace/PARTIE_16_TER_MARKETPLACE.md's
own honest-gaps section rather than claiming all 7 are wired when only
1 genuinely is.

A plugin's declared permissions (`manifest["permissions"]`) are
enforced HERE, by what this dispatcher includes in the payload handed
to the sandbox -- not inside the sandboxed process itself, which has no
ambient access to anything (see api/security/plugin_sandbox.py's own
docstring). This pass keeps every hook payload to data the caller
already has in hand (ids, filenames, event metadata) -- it does not
yet look up and attach a permission-gated read of full document/
conversation content, which would be the real next step once a hook
actually needs it.
"""

import enum
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.plugins import Plugin, PluginInstallation, PluginStatus


class PluginHook(str, enum.Enum):
    on_message_received = "on_message_received"
    on_message_sent = "on_message_sent"
    on_document_uploaded = "on_document_uploaded"
    on_agent_created = "on_agent_created"
    on_conversation_started = "on_conversation_started"
    on_error = "on_error"
    on_schedule = "on_schedule"


async def trigger_hook(db: AsyncSession, organization_id: uuid.UUID, hook: PluginHook, payload: dict) -> list:
    """Real dispatch: every enabled installation, in this organization,
    of an `approved` plugin whose manifest declares this hook, is
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

    executions = []
    for installation, plugin in rows:
        declared_hooks = (plugin.manifest or {}).get("hooks") or []
        if hook.value not in declared_hooks:
            continue
        execution = await execute_plugin(db, plugin.id, organization_id, payload, user_id=None, hook=hook.value, installation_id=installation.id)
        executions.append(execution)
    return executions
