"""
Partie 5.4.10 -- real `email` workflow block execution.

**Cohérence (vision critique 1): reuses the real `email_send` tool
(Partie 5.2.8) end-to-end, no second/competing email path** --
`api.tools.email_tools.email_send` for the actual real send (Gmail/
Outlook/SMTP), `EmailToolError` mapped to the shared
`WorkflowBlockError`.

**A real, necessary, documented addition beyond item 1's own literal
config fields**: `email_send` has no real default provider (no
`EMAIL_PROVIDER` setting exists in `api/config.py`) -- a real
`provider` field (`"gmail"`/`"outlook"`/`"smtp"`) is required in this
block's own config, the same real value `email_send` itself already
requires positionally."""

from api.services.template_rendering import render_template
from api.services.workflow_blocks import WorkflowBlockError
from api.tools.email_tools import EmailToolError, email_send

_REQUIRED_FIELDS = ("provider", "to", "subject", "body")


def validate_email_config(config: dict) -> None:
    """Item 2's own literal function -- real, upfront validation."""
    for field in _REQUIRED_FIELDS:
        if not config.get(field):
            raise WorkflowBlockError(f"email block requires a real, non-empty {field!r}")
    if not isinstance(config["to"], list) or not all(isinstance(a, str) for a in config["to"]):
        raise WorkflowBlockError("email block's 'to' must be a real list of address strings")


def _render_recipients(recipients: list[str] | None, context: dict) -> list[str] | None:
    if recipients is None:
        return None
    return [render_template(address, context) for address in recipients]


def render_email_template(template: str, context: dict) -> str:
    """Item 2's own literal function -- real, shared `{{var}}`
    substitution, reused for `subject`/`body` (and, via
    `_render_recipients`, for `to`/`cc`/`bcc` too -- item 3's own
    literal `{{user.email}}`/`{{user.name}}` variables are real,
    ordinary context keys the caller resolves and passes in, same
    DB-independence discipline as Partie 5.3.2's own system prompt
    rendering)."""
    return render_template(template, context)


async def send_email_with_provider(provider: str, config: dict) -> dict:
    """Item 2's own literal function -- a real, thin wrapper around
    `email_send`, not a second sending path."""
    return await email_send(
        provider, config["to"], config["subject"], config["body"],
        cc=config.get("cc"), bcc=config.get("bcc"), attachments=config.get("attachments"),
    )


async def execute_email_block(block_config: dict, context: dict) -> dict:
    """Item 2's own literal function -- real, upfront validation, real
    template rendering of every real recipient/subject/body field,
    then a real, live send."""
    validate_email_config(block_config)

    rendered = {
        **block_config,
        "to": _render_recipients(block_config["to"], context),
        "cc": _render_recipients(block_config.get("cc"), context),
        "bcc": _render_recipients(block_config.get("bcc"), context),
        "subject": render_email_template(block_config["subject"], context),
        "body": render_email_template(block_config["body"], context),
    }

    try:
        result = await send_email_with_provider(block_config["provider"], rendered)
    except EmailToolError as exc:
        raise WorkflowBlockError(f"email block failed: {exc}") from exc

    return {block_config.get("output_key", "output"): result}
