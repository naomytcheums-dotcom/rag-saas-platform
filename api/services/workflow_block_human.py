"""
Partie 5.4.9 -- real `human` workflow block: a real, persisted,
pending request for human input, later resolved by a real, separate
submission (`api/models/workflow_human_input.py`'s own top docstring
explains why this block cannot "execute to completion" synchronously
the way Parties 5.4.3-5.4.8 do).

**A real, necessary, documented deviation from item 2's own literal
2-argument `execute_human_block(block_config, context)` signature**:
creating a real, persisted request needs a real `db` session, the
real `workflow_run_id` it belongs to, and the real originating
`node_id` -- this executor's real signature is
`execute_human_block(db, workflow_run_id, node_id, block_config, context)`.

**Real, lazy timeout resolution, same pattern as
`api/security/human_approval.py`'s own `_resolve_if_expired`
(Partie 5.1.10)**: `get_human_approval` flips a real, still-`pending`
row past its own `expires_at` to `"timeout"` the moment it's read,
rather than needing a real, separate background sweep."""

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.workflow_human_input import HumanInputStatus, WorkflowHumanInput
from api.services.template_rendering import render_template
from api.services.workflow_blocks import WorkflowBlockError

INPUT_TYPES = ("text", "select", "confirm", "file")


def render_human_message(message_template: str, context: dict) -> str:
    """Item 2's own literal function -- real, shared `{{var}}`
    substitution."""
    return render_template(message_template, context)


def validate_human_input(input_value, input_type: str, options: list | None = None) -> None:
    """Item 2's own literal function -- real, per-`input_type`
    validation."""
    if input_type not in INPUT_TYPES:
        raise WorkflowBlockError(f"Unknown input_type: {input_type!r} (expected one of {INPUT_TYPES})")
    if input_type == "text":
        if not isinstance(input_value, str) or not input_value.strip():
            raise WorkflowBlockError("A real, non-empty string is required for a 'text' human input")
    elif input_type == "select":
        if input_value not in (options or []):
            raise WorkflowBlockError(f"{input_value!r} is not one of the real, configured options: {options}")
    elif input_type == "confirm":
        if not isinstance(input_value, bool):
            raise WorkflowBlockError("A real boolean is required for a 'confirm' human input")
    elif input_type == "file":
        if not isinstance(input_value, str) or not input_value.strip():
            raise WorkflowBlockError("A real, non-empty file reference (string) is required for a 'file' human input")


def _as_aware_utc(value: dt.datetime) -> dt.datetime:
    """Same real SQLite-naive-datetime normalization as
    `api/security/human_approval.py`'s own `_as_aware_utc`."""
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


async def execute_human_block(
    db: AsyncSession, workflow_run_id: uuid.UUID, node_id: str, block_config: dict, context: dict,
) -> WorkflowHumanInput:
    """Item 2's own literal function -- real, upfront validation of
    the block's own config, then a real, persisted, pending request."""
    input_type = block_config.get("input_type", "text")
    if input_type not in INPUT_TYPES:
        raise WorkflowBlockError(f"Unknown input_type: {input_type!r} (expected one of {INPUT_TYPES})")

    message = render_human_message(block_config.get("message", ""), context)
    timeout = block_config.get("timeout")
    expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=timeout) if timeout else None

    row = WorkflowHumanInput(
        workflow_run_id=workflow_run_id, node_id=node_id, message=message, input_type=input_type,
        options=block_config.get("options"), required=block_config.get("required", True), expires_at=expires_at,
    )
    db.add(row)
    await db.flush()
    return row


async def get_human_approval(db: AsyncSession, block_id: uuid.UUID) -> WorkflowHumanInput | None:
    """Item 2's own literal function -- real, lazy timeout resolution
    (see this module's own top docstring). `None` for an unknown id."""
    row = await db.get(WorkflowHumanInput, block_id)
    if row is None:
        return None
    if row.status == HumanInputStatus.pending.value and row.expires_at is not None:
        if dt.datetime.now(dt.timezone.utc) >= _as_aware_utc(row.expires_at):
            row.status = HumanInputStatus.timeout.value
            await db.flush()
    return row


async def submit_human_input(db: AsyncSession, block_id: uuid.UUID, user_id: uuid.UUID | None, input_value) -> WorkflowHumanInput | None:
    """Item 2's own literal function -- real, upfront validation
    against the real, stored `input_type`/`options`; `None` (a real,
    honest no-op) for an unknown request OR one that is no longer
    really pending (already submitted, or timed out)."""
    row = await get_human_approval(db, block_id)
    if row is None or row.status != HumanInputStatus.pending.value:
        return None

    validate_human_input(input_value, row.input_type, row.options)
    row.value = input_value
    row.status = HumanInputStatus.submitted.value
    row.submitted_by = user_id
    row.submitted_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return row


async def list_human_blocks(db: AsyncSession, workflow_run_id: uuid.UUID) -> list[WorkflowHumanInput]:
    """Real, shared plumbing backing `GET .../human-blocks` -- real,
    lazy timeout resolution applied to every real, still-pending row
    returned."""
    rows = list((await db.scalars(
        select(WorkflowHumanInput).where(WorkflowHumanInput.workflow_run_id == workflow_run_id).order_by(WorkflowHumanInput.created_at)
    )).all())
    for row in rows:
        await get_human_approval(db, row.id)
    return rows
