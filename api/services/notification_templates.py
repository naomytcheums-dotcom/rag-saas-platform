"""
Phase 5, Étape 4 -- Jinja2 templates for notifications, code-defined
rather than DB-backed. See api/models/notification.py's own docstring
for why: a full admin-editable `NotificationTemplate` CRUD + preview UI
is real, additional scope this étape doesn't build (traced in
ROADMAP.md); what's here is real, working, and covers every
notification type this étape actually wires end-to-end.

Jinja2's own autoescape is turned on for every template (both `title`
and `body` are rendered as HTML-safe by default) -- a notification's
`data` dict can legitimately contain a user-supplied string (e.g. an
organization name, an invitee's own display name) that must never be
interpreted as markup once rendered into an email or the in-app UI.
"""

import jinja2

_ENV = jinja2.Environment(autoescape=True, undefined=jinja2.StrictUndefined)

TEMPLATES: dict[str, dict[str, str]] = {
    "job_completed": {
        "title": "Document processing completed",
        "body": "Your document '{{ document_name }}' has finished processing and is ready to search.",
        "email_subject": "Your document is ready: {{ document_name }}",
    },
    "job_failed": {
        "title": "Document processing failed",
        "body": "Your document '{{ document_name }}' failed to process. {{ error | default('An unexpected error occurred.') }}",
        "email_subject": "Document processing failed: {{ document_name }}",
    },
    "workflow_completed": {
        "title": "Workflow completed",
        "body": "Your workflow '{{ workflow_name }}' completed successfully.",
        "email_subject": "Workflow completed: {{ workflow_name }}",
    },
    "workflow_failed": {
        "title": "Workflow failed",
        "body": "Your workflow '{{ workflow_name }}' failed. {{ error | default('An unexpected error occurred.') }}",
        "email_subject": "Workflow failed: {{ workflow_name }}",
    },
    "billing_payment_failed": {
        "title": "Payment failed",
        "body": "A payment for {{ organization_name }} failed. Please update your payment method to avoid service interruption.",
        "email_subject": "Action needed: payment failed for {{ organization_name }}",
    },
    "invitation_received": {
        "title": "You've been invited to join {{ organization_name }}",
        "body": "You've been invited to join {{ organization_name }} as {{ role }}.",
        "email_subject": "You've been invited to join {{ organization_name }}",
    },
    "security_login_new_device": {
        "title": "New login detected",
        "body": "A new login to your account was detected from {{ device_info | default('an unrecognized device') }}.",
        "email_subject": "New login to your account",
    },
    "security_password_changed": {
        "title": "Password changed",
        "body": "Your account password was just changed.",
        "email_subject": "Your password was changed",
    },
    "workflow_approval_needed": {
        "title": "Approval needed",
        "body": "Your workflow '{{ workflow_name }}' is waiting on your approval: {{ message }}",
        "email_subject": "Approval needed: {{ workflow_name }}",
    },
    "security_2fa_enabled": {
        "title": "Two-factor authentication enabled",
        "body": "Two-factor authentication was just enabled on your account.",
        "email_subject": "Two-factor authentication enabled",
    },
}

_GENERIC_TEMPLATE = {
    "title": "{{ title }}",
    "body": "{{ body }}",
    "email_subject": "{{ title }}",
}


def render_notification(notification_type: str, context: dict) -> dict:
    """Returns {"title", "body", "email_subject"}, all rendered. An
    unknown `notification_type` renders through `_GENERIC_TEMPLATE`,
    which just echoes back `context["title"]`/`context["body"]`
    verbatim (still real, still escaped) -- a caller with a genuinely
    new notification type is never blocked from sending one, it just
    doesn't get a purpose-written template until one is added above."""
    template = TEMPLATES.get(notification_type, _GENERIC_TEMPLATE)
    return {key: _ENV.from_string(value).render(**context) for key, value in template.items()}
