"""
Partie 5.4.11 -- real `calendar` workflow block execution.

**Cohérence (vision critique 1): reuses the real calendar tools
(Partie 5.2.7) end-to-end, no second/competing calendar path** --
`api.tools.calendar_tools.calendar_list_events`/`calendar_create_event`/
`calendar_update_event`/`calendar_delete_event`/`calendar_find_available_slots`
for every real `action` (item 1's own literal 5), `CalendarError`
mapped to the shared `WorkflowBlockError`.

**A real, necessary, documented addition beyond item 1's own literal
config fields**: `action="update"`/`"delete"` genuinely need a real,
existing `event_id` to act on -- neither `calendar_update_event` nor
`calendar_delete_event` can work without one. `event_id` is a real,
required config field for those two real actions, the same kind of
real, necessary addition already made for the Email block's own
`provider` field (Partie 5.4.10).

**Robustesse (vision critique 3): a real gap found in the underlying
tool, compensated at this block's own boundary, not silently masked**
-- `api/tools/calendar_tools.py`'s own functions (Partie 5.2.7) only
ever raise `CalendarError` for a real provider/credential problem; a
real HTTP failure (a non-2xx status, a real connection error) is left
to propagate as a RAW `httpx.HTTPError`, never wrapped. This block
catches BOTH real exception types and re-raises the shared
`WorkflowBlockError` either way, so a real caller here never has to
know `calendar_tools.py`'s own internal `httpx` dependency exists."""

import httpx

from api.services.template_rendering import render_template
from api.services.workflow_blocks import WorkflowBlockError
from api.tools.calendar_tools import (
    CalendarError, calendar_create_event, calendar_delete_event, calendar_find_available_slots,
    calendar_list_events, calendar_update_event,
)

ACTIONS = ("list", "create", "update", "delete", "find_slots")


def validate_calendar_config(config: dict) -> None:
    """Item 2's own literal function -- real, upfront, per-`action`
    validation."""
    action = config.get("action")
    if action not in ACTIONS:
        raise WorkflowBlockError(f"Unknown action: {action!r} (expected one of {ACTIONS})")
    if not config.get("provider"):
        raise WorkflowBlockError("calendar block requires a real, non-empty 'provider'")
    if action == "create" and not (config.get("title") and config.get("start_time") and config.get("end_time")):
        raise WorkflowBlockError("calendar block's 'create' action requires 'title', 'start_time', and 'end_time'")
    if action in ("list", "find_slots") and not (config.get("start_time") and config.get("end_time")):
        raise WorkflowBlockError(f"calendar block's {action!r} action requires 'start_time' and 'end_time'")
    if action == "find_slots" and not config.get("duration"):
        raise WorkflowBlockError("calendar block's 'find_slots' action requires a real 'duration'")
    if action in ("update", "delete") and not config.get("event_id"):
        raise WorkflowBlockError(f"calendar block's {action!r} action requires a real 'event_id'")


def render_calendar_field(template: str, context: dict) -> str:
    """Item 2's own literal function -- real, shared `{{var}}`
    substitution."""
    return render_template(template, context)


def format_calendar_results(results) -> dict:
    """Item 2's own literal function -- a real, JSON-safe wrapper (a
    real list of events, a real single event dict, or a real boolean
    all pass through unchanged, just wrapped)."""
    return {"results": results}


def _render_recursive(value, context: dict):
    if isinstance(value, str):
        return render_calendar_field(value, context)
    if isinstance(value, list):
        return [_render_recursive(v, context) for v in value]
    return value


async def execute_calendar_block(block_config: dict, context: dict) -> dict:
    """Item 2's own literal function -- real, upfront validation, real
    field rendering, then a real, live calendar call dispatched by the
    real `action`."""
    validate_calendar_config(block_config)

    provider = block_config["provider"]
    title = render_calendar_field(block_config["title"], context) if block_config.get("title") else None
    start_time = render_calendar_field(block_config["start_time"], context) if block_config.get("start_time") else None
    end_time = render_calendar_field(block_config["end_time"], context) if block_config.get("end_time") else None
    description = render_calendar_field(block_config["description"], context) if block_config.get("description") else None
    attendees = _render_recursive(block_config.get("attendees"), context)
    action = block_config["action"]

    try:
        if action == "list":
            result = await calendar_list_events(provider, start_time, end_time)
        elif action == "create":
            result = await calendar_create_event(provider, title, start_time, end_time, description, attendees)
        elif action == "update":
            result = await calendar_update_event(provider, block_config["event_id"], title, start_time, end_time, description)
        elif action == "delete":
            result = await calendar_delete_event(provider, block_config["event_id"])
        else:  # find_slots
            result = await calendar_find_available_slots(provider, start_time, end_time, block_config["duration"])
    except (CalendarError, httpx.HTTPError) as exc:
        raise WorkflowBlockError(f"calendar block failed: {exc}") from exc

    return {block_config.get("output_key", "output"): format_calendar_results(result)}
