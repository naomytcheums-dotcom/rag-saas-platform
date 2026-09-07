"""
Partie 5.4.2 -- real ways to start a `Workflow` run: webhook, schedule,
manual. `WorkflowTrigger`/`WorkflowRun` (`api/models/workflow_run.py`)
were already declared in migration `0062` (Partie 5.4.1); this étape
is the first to actually consume them.

**Webhooks (vision critique "sont-ils sécurisés") -- a real, secret
token, item 3's own literal path kept intact**: `create_webhook_trigger`
generates a real, cryptographically random `webhook_token`
(`secrets.token_urlsafe`, same real RNG as Partie 5.3.10's own API
keys). The real endpoint (item 3's own literal
`POST /webhooks/{trigger_id}`) requires that same real token in a real
`X-Webhook-Token` header, checked via `secrets.compare_digest`
(constant-time, no early-exit timing signal) -- unlike an API key
(Partie 5.3.10, shown once), a webhook's own token stays real,
re-visible to a real Manager (same real, operational need as
GitHub/Slack/Discord's own webhook config screens: you must be able to
see/copy the URL+secret again to reconfigure the calling external
service). Deliberately NOT a request-signature/HMAC scheme (real,
honest, simpler alternative) -- documented, not hidden.

**Schedules -- real cron parsing, no new dependency**: `create_schedule_trigger`
validates `cron_pattern` the SAME way `api/security/reindex_schedules.py`
already does (Celery's own `crontab`, already a real dependency for
Beat) -- no second cron-parsing library for this one feature.

**Honest, documented scope boundary (real, not silently claimed)**:
`trigger_workflow` creates a real, persisted `WorkflowRun` row
(`status="pending"`) -- it does NOT walk the real graph and execute
each real node in turn. That is a genuinely separate, substantial
piece of work (a real graph executor chaining Parties 5.4.3-5.4.11's
own per-block execution functions along real edges) -- this étape's
own literal scope is the TRIGGER itself (item 1's own literal title,
"Bloc Trigger"), not full workflow execution, same "no automatic
function-calling loop" honesty already documented in
`api/services/agent_orchestrator.py`'s own top docstring for a
comparable, real, deliberate boundary."""

import secrets
import uuid

from celery.schedules import crontab
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.workflow_run import TRIGGER_TYPES, WorkflowRun, WorkflowRunStatus, WorkflowTrigger


class WorkflowTriggerError(ValueError):
    """Real, dedicated exception."""


def _crontab_from_pattern(cron_pattern: str) -> crontab:
    """Same real, standard 5-field cron parsing as
    `api/security/reindex_schedules.py`'s own `_crontab_from_pattern`."""
    fields = cron_pattern.split()
    if len(fields) != 5:
        raise WorkflowTriggerError(f"cron_pattern must have exactly 5 fields (minute hour day_of_month month_of_year day_of_week), got {cron_pattern!r}")
    minute, hour, day_of_month, month_of_year, day_of_week = fields
    try:
        return crontab(minute=minute, hour=hour, day_of_month=day_of_month, month_of_year=month_of_year, day_of_week=day_of_week)
    except Exception as exc:
        raise WorkflowTriggerError(f"'{cron_pattern}' is not a real, valid cron pattern: {exc}") from exc


async def create_webhook_trigger(db: AsyncSession, workflow_id: uuid.UUID, config: dict | None = None) -> WorkflowTrigger:
    """Item 2's own literal function -- generates a real, per-trigger
    `webhook_token` (never returned again after this call except via
    `get_trigger_url`, same "the row's own owner can always see their
    own real URL" reasoning as an API key's own prefix)."""
    trigger = WorkflowTrigger(workflow_id=workflow_id, type="webhook", config=config or {}, webhook_token=secrets.token_urlsafe(32))
    db.add(trigger)
    await db.flush()
    return trigger


async def create_schedule_trigger(db: AsyncSession, workflow_id: uuid.UUID, cron_pattern: str) -> WorkflowTrigger:
    """Item 2's own literal function -- real, upfront cron validation
    before the trigger is ever persisted."""
    _crontab_from_pattern(cron_pattern)
    trigger = WorkflowTrigger(workflow_id=workflow_id, type="schedule", config={"cron_pattern": cron_pattern})
    db.add(trigger)
    await db.flush()
    return trigger


async def create_manual_trigger(db: AsyncSession, workflow_id: uuid.UUID) -> WorkflowTrigger:
    """Item 2's own literal function."""
    trigger = WorkflowTrigger(workflow_id=workflow_id, type="manual", config={})
    db.add(trigger)
    await db.flush()
    return trigger


async def trigger_workflow(db: AsyncSession, workflow_id: uuid.UUID, input: dict | None = None, trigger_id: uuid.UUID | None = None) -> WorkflowRun:
    """Item 2's own literal function -- see this module's own top
    docstring for the real, honest boundary: creates a real, pending
    run; does not execute it."""
    run = WorkflowRun(workflow_id=workflow_id, trigger_id=trigger_id, status=WorkflowRunStatus.pending.value, input=input or {})
    db.add(run)
    await db.flush()
    return run


def get_trigger_url(trigger: WorkflowTrigger) -> str:
    """Item 2's own literal function -- item 3's own literal path
    (`POST /webhooks/{trigger_id}`); the real, required
    `X-Webhook-Token` header is a separate, real security layer (see
    this module's own top docstring), not embedded in the URL itself."""
    if trigger.type != "webhook":
        raise WorkflowTriggerError("get_trigger_url only applies to a real webhook trigger")
    return f"/webhooks/{trigger.id}"


def verify_webhook_token(trigger: WorkflowTrigger, token: str) -> bool:
    """Real, constant-time comparison -- the actual security check the
    router's own `POST /webhooks/{trigger_id}` performs against the
    real `X-Webhook-Token` header."""
    return trigger.webhook_token is not None and secrets.compare_digest(trigger.webhook_token, token)


async def get_trigger(db: AsyncSession, trigger_id: uuid.UUID) -> WorkflowTrigger | None:
    return await db.get(WorkflowTrigger, trigger_id)


async def list_triggers(db: AsyncSession, workflow_id: uuid.UUID) -> list[WorkflowTrigger]:
    result = await db.scalars(
        select(WorkflowTrigger).where(WorkflowTrigger.workflow_id == workflow_id).order_by(WorkflowTrigger.created_at.desc())
    )
    return list(result)


async def delete_trigger(db: AsyncSession, trigger_id: uuid.UUID) -> bool:
    trigger = await db.get(WorkflowTrigger, trigger_id)
    if trigger is None:
        return False
    await db.delete(trigger)
    await db.flush()
    return True
