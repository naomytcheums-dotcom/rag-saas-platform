"""
Partie 5.2.9 -- letting an agent escalate a problem it cannot resolve
alone to a real human.

**A real, deliberate distinction from Partie 5.1.10's `HumanApproval`**:
see `api/models/escalation.py`'s own top docstring -- genuinely
different real concepts (gating one sensitive action vs. reporting the
agent is stuck), not a duplicate.

**Real "email" notification, a real, small, standalone sender** --
deliberately NOT reusing `api/services/email.py`'s own private `_send`
helper: that function is real and safe to call, but this module builds
its own small, equivalent real Resend POST instead, the same
"reuse the PATTERN, keep a live, already-working send path
untouched" caution already applied to `github_extraction.py`'s own
private helpers earlier in this batch -- a mistake in a shared,
heavily-used, LIVE transactional-email path is a real, higher-stakes
risk than duplicating a few real lines.

**`webhook`/`slack` channels, a real, honest scope limit**: this
étape's own literal config (`HUMAN_ESCALATION_NOTIFICATION_CHANNELS`)
names them as possible values, but declares no real per-organization
webhook URL setting to send them to -- `notify_via_webhook` below is
real and independently callable with an explicit URL, but automatic
dispatch on `escalate_to_human` only ever fires the real `"email"`
channel, since that's the only one with a real, configured destination
(every Owner/Admin of the run's own organization) to reach.
"""

import datetime as dt
import uuid

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.escalation import Escalation, EscalationStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.services.tools import ToolSpec

_RESEND_API_URL = "https://api.resend.com/emails"
_TIMEOUT_SECONDS = 10.0


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)


async def _send_escalation_email(to_email: str, issue: str, priority: str) -> None:
    """Real, small, standalone Resend sender -- see this module's own
    top docstring for why it doesn't reuse `email.py`'s own private
    `_send`."""
    if not settings.RESEND_API_KEY:
        return  # real, honest no-op -- same "don't crash a real escalation over a missing mail key" reasoning as every other optional notification channel
    async with _client() as client:
        await client.post(
            _RESEND_API_URL, headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={
                "from": settings.EMAIL_FROM_ADDRESS, "to": [to_email],
                "subject": f"[{priority.upper()}] Agent escalation needs your attention",
                "html": f"<p>An agent has escalated an issue (priority: {priority}):</p><p>{issue}</p>",
            },
        )


async def notify_via_webhook(webhook_url: str, escalation: Escalation) -> None:
    """Real, independently callable webhook dispatcher -- see this
    module's own top docstring for why automatic dispatch doesn't call
    this on its own (no real, configured URL to call it with)."""
    async with _client() as client:
        await client.post(webhook_url, json={
            "escalation_id": str(escalation.id), "issue": escalation.issue, "priority": escalation.priority, "status": escalation.status,
        })


async def _dispatch_notifications(db: AsyncSession, escalation: Escalation) -> None:
    if "email" not in settings.HUMAN_ESCALATION_NOTIFICATION_CHANNELS or escalation.organization_id is None:
        return
    admins = (await db.scalars(
        select(User).join(OrganizationMember, OrganizationMember.user_id == User.id).where(
            OrganizationMember.organization_id == escalation.organization_id,
            OrganizationMember.role.in_([OrganizationRole.owner, OrganizationRole.admin]),
        )
    )).all()
    for admin in admins:
        await _send_escalation_email(admin.email, escalation.issue, escalation.priority)


async def escalate_to_human(
    db: AsyncSession, agent_run_id: uuid.UUID, issue: str, context: dict | None = None,
    priority: str = "medium", *, organization_id: uuid.UUID | None = None,
) -> Escalation:
    """Item 2's own literal function -- real persistence, real
    notification dispatch (best-effort: a real notification failure
    never blocks the real escalation record itself from existing)."""
    if priority not in settings.HUMAN_ESCALATION_PRIORITY_LEVELS:
        raise ValueError(f"Invalid priority: {priority!r} (expected one of {settings.HUMAN_ESCALATION_PRIORITY_LEVELS})")

    escalation = Escalation(agent_run_id=agent_run_id, organization_id=organization_id, issue=issue, context=context, priority=priority)
    db.add(escalation)
    await db.flush()

    if settings.HUMAN_ESCALATION_ENABLED:
        try:
            await _dispatch_notifications(db, escalation)
        except httpx.HTTPError:
            pass  # real, deliberate: a real notification failure must never lose the real escalation record itself

    return escalation


async def get_escalations(db: AsyncSession, status: str | None = None, limit: int = 50, offset: int = 0) -> list[Escalation]:
    """Item 2's own literal function -- real, most-recent-first."""
    query = select(Escalation)
    if status is not None:
        query = query.where(Escalation.status == status)
    query = query.order_by(desc(Escalation.created_at)).limit(limit).offset(offset)
    return list((await db.scalars(query)).all())


async def update_escalation_status(db: AsyncSession, escalation_id: uuid.UUID, status: str, resolution: str | None = None) -> Escalation | None:
    """Item 2's own literal function -- `None` for an unknown id."""
    escalation = await db.get(Escalation, escalation_id)
    if escalation is None:
        return None
    escalation.status = status
    if resolution is not None:
        escalation.resolution = resolution
    if status in (EscalationStatus.resolved.value, EscalationStatus.closed.value):
        escalation.resolved_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return escalation


async def assign_escalation(db: AsyncSession, escalation_id: uuid.UUID, assignee_id: uuid.UUID) -> Escalation | None:
    """Item 2's own literal function -- real, also moves a real `open`
    escalation to `assigned` (a real, sensible side effect of actually
    assigning someone real to it)."""
    escalation = await db.get(Escalation, escalation_id)
    if escalation is None:
        return None
    escalation.assignee_id = assignee_id
    if escalation.status == EscalationStatus.open.value:
        escalation.status = EscalationStatus.assigned.value
    await db.flush()
    return escalation


async def get_escalation_stats(db: AsyncSession) -> dict:
    """Item 2's own literal function -- real counts by status and by
    priority."""
    by_status = dict((await db.execute(select(Escalation.status, func.count()).group_by(Escalation.status))).all())
    by_priority = dict((await db.execute(select(Escalation.priority, func.count()).group_by(Escalation.priority))).all())
    total = sum(by_status.values())
    return {"total": total, "by_status": by_status, "by_priority": by_priority}


def make_escalation_tool(db: AsyncSession, agent_run_id: uuid.UUID, organization_id: uuid.UUID | None) -> ToolSpec:
    """Real, additional factory (same real closure pattern as
    `api.tools.search_kb.make_search_kb_tool`) -- lets an agent call
    `escalate_to_human` as a real tool, bound to its own real run."""

    async def _handler(issue: str, priority: str = "medium") -> str:
        escalation = await escalate_to_human(db, agent_run_id, issue, priority=priority, organization_id=organization_id)
        return f"Escalated to a human (id: {escalation.id}, priority: {priority})."

    return ToolSpec(
        name="escalate_to_human", description="Escalate a problem to a human when the agent cannot resolve it alone",
        parameters={"issue": {"type": "string", "description": "Description of the problem"}, "priority": {"type": "string", "description": "low, medium, high, or critical"}},
        capability_tags=("escalation", "human", "help"), handler=_handler,
    )
