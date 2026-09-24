"""
Phase 5, Étape 3 -- real email branding, closing a genuine gap the
White Label audit surfaced: `OrganizationBranding.email_sender_name`/
`email_sender_email`/`logo_url` (api/models/organization_branding.py)
have existed since Partie 1.3.10/19, configurable through
`POST /organizations/{org_id}/whitelabel/email` and the branding PATCH
endpoints -- but `api/services/email.py` never reads them when
composing any of its ~30 `send_*_email` functions. An org could
configure a branded sender identity and it would have zero effect on
any email actually sent.

**Honest, deliberately narrow scope**: rewiring every one of those ~30
functions (and every one of their call sites, several of which are
platform-level auth emails sent before a user even has an
organization context, e.g. password reset) is a much larger refactor
that overlaps with the explicitly out-of-scope "Notifications" étape
(see this étape's own spec, section 8). This module builds the real,
working, tested branding-composition primitives, and wires them into
ONE real, representative, high-value call site --
`send_branded_organization_invitation_email`, used by
`api/routers/invitations.py` -- as genuine, working proof this closes
for real, not just in theory. The other ~29 functions are traced,
not silently left inconsistent -- see ROADMAP.md's own entry.
"""

import asyncio
import html
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.organization import Organization
from api.models.organization_branding import OrganizationBranding
from api.services.email import _send


async def get_active_branding(db: AsyncSession, organization_id: uuid.UUID) -> OrganizationBranding | None:
    """None for "no branding configured" AND for "configured but
    is_active=False" -- both mean "render pure platform defaults",
    the exact same real distinction api/models/organization_branding.py's
    own docstring already establishes for is_active."""
    branding = await db.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id == organization_id))
    if branding is None or not branding.is_active:
        return None
    return branding


def compose_branded_from_address(branding: OrganizationBranding | None) -> str:
    """Resend's REST API accepts `"from": "Display Name <email@domain>"`
    directly (api/services/email.py's own `_send` passes `from_address`
    through verbatim) -- no change to `_send` itself needed."""
    if branding is not None and branding.email_sender_name and branding.email_sender_email:
        return f"{branding.email_sender_name} <{branding.email_sender_email}>"
    return settings.EMAIL_FROM_ADDRESS


def render_branded_header(branding: OrganizationBranding | None) -> str:
    if branding is not None and branding.logo_url:
        return f'<p><img src="{html.escape(branding.logo_url)}" alt="" style="max-height:48px;max-width:200px"></p>'
    return ""


def render_branded_footer(branding: OrganizationBranding | None) -> str:
    """Distinct from api/services/email._send's own unconditional RGPD
    support-footer (always appended, platform-level, never skipped) --
    this is an ADDITIONAL, org-specific line shown only when the org
    configured company_email/support_email, giving the recipient the
    org's own contact info, not just the platform's."""
    if branding is None or not (branding.company_email or branding.support_email):
        return ""
    contacts = " / ".join(html.escape(e) for e in (branding.company_email, branding.support_email) if e)
    return f"<p style='color:#666;font-size:12px'>Contact: {contacts}</p>"


async def send_branded_organization_invitation_email(
    db: AsyncSession, organization_id: uuid.UUID, to_email: str, role: str, invite_link: str,
) -> None:
    """Branded equivalent of api/services/email.send_organization_invitation_email
    -- same content/behavior, but the sender identity, a logo header,
    and an org-contact footer are pulled from this organization's real,
    active OrganizationBranding when one exists (falling back to
    exactly the platform defaults the un-branded function already used
    when it doesn't, so an org with no branding configured sees zero
    behavior change)."""
    organization = await db.get(Organization, organization_id)
    branding = await get_active_branding(db, organization_id)
    organization_name = organization.name if organization else str(organization_id)

    subject = f"You've been invited to join {organization_name}"
    body = (
        f"{render_branded_header(branding)}"
        f"<p>You've been invited to join <strong>{html.escape(organization_name)}</strong> "
        f"as <strong>{html.escape(role)}</strong>.</p>"
        f"<p>Click the link below to accept. It expires in {settings.INVITATION_EXPIRE_DAYS} days.</p>"
        f'<p><a href="{invite_link}">{invite_link}</a></p>'
        f"<p>If you don't recognize this organization, you can safely ignore this email.</p>"
        f"{render_branded_footer(branding)}"
    )
    from_address = compose_branded_from_address(branding)

    # `_send` is a synchronous, blocking `httpx.post` call (Resend has no
    # async SDK here) -- offloaded to a thread so it never blocks the
    # event loop, same reason api/routers/invitations.py's own
    # pre-existing call site wrapped the un-branded version in
    # `asyncio.to_thread` before this function existed.
    await asyncio.to_thread(_send, to_email, subject, body, from_address)


# ---------------------------------------------------------------------------
# Phase 5, Étape 3 (suite) -- real branded versions of the 7 remaining
# org-level emails. Same pattern as send_branded_organization_invitation_email
# above: same content/behavior, but sender identity, logo header, and
# org-contact footer come from the organization's real, active
# OrganizationBranding when one exists -- falling back to exactly the
# platform defaults the un-branded function already used when it doesn't.
#
# The auth/security (~20) and user-level (~8) emails are deliberately
# NOT branded: they are sent before a user has an organization context
# (password reset, 2FA, login) or are user-scoped, not org-scoped.
# ---------------------------------------------------------------------------


async def send_branded_organization_member_added_email(
    db: AsyncSession, organization_id: uuid.UUID, to_email: str, role: str,
) -> None:
    """Branded equivalent of send_organization_member_added_email."""
    organization = await db.get(Organization, organization_id)
    branding = await get_active_branding(db, organization_id)
    organization_name = organization.name if organization else str(organization_id)

    subject = f"You've been added to {organization_name}"
    body = (
        f"{render_branded_header(branding)}"
        f"<p>You were just added to the organization <strong>{html.escape(organization_name)}</strong> "
        f"as <strong>{html.escape(role)}</strong>.</p>"
        f"{render_branded_footer(branding)}"
    )
    from_address = compose_branded_from_address(branding)
    await asyncio.to_thread(_send, to_email, subject, body, from_address)


async def send_branded_organization_member_role_changed_email(
    db: AsyncSession, organization_id: uuid.UUID, to_email: str, new_role: str,
) -> None:
    """Branded equivalent of send_organization_member_role_changed_email."""
    organization = await db.get(Organization, organization_id)
    branding = await get_active_branding(db, organization_id)
    organization_name = organization.name if organization else str(organization_id)

    subject = f"Your role in {organization_name} was changed"
    body = (
        f"{render_branded_header(branding)}"
        f"<p>Your role in <strong>{html.escape(organization_name)}</strong> was just changed to "
        f"<strong>{html.escape(new_role)}</strong>.</p>"
        f"{render_branded_footer(branding)}"
    )
    from_address = compose_branded_from_address(branding)
    await asyncio.to_thread(_send, to_email, subject, body, from_address)


async def send_branded_organization_member_removed_email(
    db: AsyncSession, organization_id: uuid.UUID, to_email: str,
) -> None:
    """Branded equivalent of send_organization_member_removed_email."""
    organization = await db.get(Organization, organization_id)
    branding = await get_active_branding(db, organization_id)
    organization_name = organization.name if organization else str(organization_id)

    subject = f"You were removed from {organization_name}"
    body = (
        f"{render_branded_header(branding)}"
        f"<p>You were just removed from the organization <strong>{html.escape(organization_name)}</strong>.</p>"
        f"<p>If you believe this was a mistake, contact your organization's administrator.</p>"
        f"{render_branded_footer(branding)}"
    )
    from_address = compose_branded_from_address(branding)
    await asyncio.to_thread(_send, to_email, subject, body, from_address)


async def send_branded_invoice_email(
    db: AsyncSession, organization_id: uuid.UUID, to_email: str, invoice_number: str, total_display: str,
) -> None:
    """Branded equivalent of send_invoice_email."""
    organization = await db.get(Organization, organization_id)
    branding = await get_active_branding(db, organization_id)
    organization_name = organization.name if organization else str(organization_id)

    subject = f"Invoice {invoice_number} for {organization_name}"
    body = (
        f"{render_branded_header(branding)}"
        f"<p>Your invoice <strong>{html.escape(invoice_number)}</strong> ({html.escape(total_display)}) "
        f"is ready. Sign in to your billing dashboard to view or download it.</p>"
        f"{render_branded_footer(branding)}"
    )
    from_address = compose_branded_from_address(branding)
    await asyncio.to_thread(_send, to_email, subject, body, from_address)


async def send_branded_invoice_reminder_email(
    db: AsyncSession, organization_id: uuid.UUID, to_email: str, invoice_number: str, total_display: str, days_overdue: int,
) -> None:
    """Branded equivalent of send_invoice_reminder_email."""
    organization = await db.get(Organization, organization_id)
    branding = await get_active_branding(db, organization_id)
    organization_name = organization.name if organization else str(organization_id)

    subject = f"Reminder: invoice {invoice_number} for {organization_name} is overdue"
    body = (
        f"{render_branded_header(branding)}"
        f"<p>Invoice <strong>{html.escape(invoice_number)}</strong> ({html.escape(total_display)}) "
        f"is now {days_overdue} day(s) overdue. Please arrange payment.</p>"
        f"{render_branded_footer(branding)}"
    )
    from_address = compose_branded_from_address(branding)
    await asyncio.to_thread(_send, to_email, subject, body, from_address)


async def send_branded_usage_limit_warning_email(
    db: AsyncSession, organization_id: uuid.UUID, to_email: str, resource_type: str, current_percent: int, limit: int,
) -> None:
    """Branded equivalent of send_usage_limit_warning_email."""
    organization = await db.get(Organization, organization_id)
    branding = await get_active_branding(db, organization_id)
    organization_name = organization.name if organization else str(organization_id)

    subject = f"{organization_name} is at {current_percent}% of its {resource_type} limit"
    body = (
        f"{render_branded_header(branding)}"
        f"<p>Your organization <strong>{html.escape(organization_name)}</strong> is using "
        f"{current_percent}% of its plan's {html.escape(resource_type)} limit ({html.escape(str(limit))} total). "
        f"Consider upgrading your plan before you hit it.</p>"
        f"{render_branded_footer(branding)}"
    )
    from_address = compose_branded_from_address(branding)
    await asyncio.to_thread(_send, to_email, subject, body, from_address)


async def send_branded_analytics_report_email(
    db: AsyncSession, organization_id: uuid.UUID, to_email: str, total_events_last_30d: int,
) -> None:
    """Branded equivalent of send_analytics_report_email. The original
    takes no organization context at all -- this one adds it, since a
    branding decision requires knowing which org is sending."""
    organization = await db.get(Organization, organization_id)
    branding = await get_active_branding(db, organization_id)
    organization_name = organization.name if organization else str(organization_id)

    subject = f"Your monthly analytics report -- {organization_name}"
    body = (
        f"{render_branded_header(branding)}"
        f"<p>Your organization tracked <strong>{total_events_last_30d}</strong> product events in the last 30 days. "
        f"Sign in to your analytics dashboard for the full breakdown.</p>"
        f"{render_branded_footer(branding)}"
    )
    from_address = compose_branded_from_address(branding)
    await asyncio.to_thread(_send, to_email, subject, body, from_address)


# ---------------------------------------------------------------------------
# Sync variants for Celery tasks (which use SyncSession, not AsyncSession).
# The async versions above are for FastAPI request handlers. Celery tasks
# run in a sync context and cannot `await` -- these variants take a plain
# sync SQLAlchemy Session and do the branding lookup synchronously.
# ---------------------------------------------------------------------------


def _sync_get_active_branding(db, organization_id):
    """Sync equivalent of get_active_branding for Celery tasks."""
    branding = db.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id == organization_id))
    if branding is None or not branding.is_active:
        return None
    return branding


def _sync_get_organization_name(db, organization_id):
    """Sync lookup of the org name, falling back to the str(id)."""
    org = db.get(Organization, organization_id)
    return org.name if org else str(organization_id)


def send_branded_invoice_reminder_email_sync(
    db, organization_id: uuid.UUID, to_email: str, invoice_number: str, total_display: str, days_overdue: int,
) -> None:
    """Sync branded equivalent of send_invoice_reminder_email, for
    api/tasks/billing.py's own send_invoice_reminders task."""
    branding = _sync_get_active_branding(db, organization_id)
    organization_name = _sync_get_organization_name(db, organization_id)

    subject = f"Reminder: invoice {invoice_number} for {organization_name} is overdue"
    body = (
        f"{render_branded_header(branding)}"
        f"<p>Invoice <strong>{html.escape(invoice_number)}</strong> ({html.escape(total_display)}) "
        f"is now {days_overdue} day(s) overdue. Please arrange payment.</p>"
        f"{render_branded_footer(branding)}"
    )
    from_address = compose_branded_from_address(branding)
    _send(to_email, subject, body, from_address)


def send_branded_usage_limit_warning_email_sync(
    db, organization_id: uuid.UUID, to_email: str, resource_type: str, current_percent: int, limit: int,
) -> None:
    """Sync branded equivalent of send_usage_limit_warning_email, for
    api/tasks/sales.py's own check_usage_limits sweep."""
    branding = _sync_get_active_branding(db, organization_id)
    organization_name = _sync_get_organization_name(db, organization_id)

    subject = f"{organization_name} is at {current_percent}% of its {resource_type} limit"
    body = (
        f"{render_branded_header(branding)}"
        f"<p>Your organization <strong>{html.escape(organization_name)}</strong> is using "
        f"{current_percent}% of its plan's {html.escape(resource_type)} limit ({html.escape(str(limit))} total). "
        f"Consider upgrading your plan before you hit it.</p>"
        f"{render_branded_footer(branding)}"
    )
    from_address = compose_branded_from_address(branding)
    _send(to_email, subject, body, from_address)


def send_branded_analytics_report_email_sync(
    db, organization_id: uuid.UUID, to_email: str, total_events_last_30d: int,
) -> None:
    """Sync branded equivalent of send_analytics_report_email, for
    api/tasks/analytics.py's own send_analytics_report task."""
    branding = _sync_get_active_branding(db, organization_id)
    organization_name = _sync_get_organization_name(db, organization_id)

    subject = f"Your monthly analytics report -- {organization_name}"
    body = (
        f"{render_branded_header(branding)}"
        f"<p>Your organization tracked <strong>{total_events_last_30d}</strong> product events in the last 30 days. "
        f"Sign in to your analytics dashboard for the full breakdown.</p>"
        f"{render_branded_footer(branding)}"
    )
    from_address = compose_branded_from_address(branding)
    _send(to_email, subject, body, from_address)
