"""
Partie 5.3.2 -- real, safe `{{variable}}` templating for an agent's own
system prompt.

**A real, deliberate choice: a hand-written, regex-based `{{var}}`
substitution, NOT Python's own `str.format()`/`str.format_map()`**
(vision critique: "les templates sont-ils protégés contre les
injections ?"). `format_map` executed against an attacker-influenced
format STRING is a real, documented Python vulnerability class
(`"{0.__class__.__init__.__globals__[...]}".format_map(...)`-style
attribute-traversal payloads) -- a real risk here since a template's
own AUTHOR (an Owner/Admin/Manager, real but not necessarily fully
trusted with arbitrary code execution) controls the format STRING
itself, not just the values substituted into it. A real, minimal regex
match-and-replace on a fixed `\\{\\{(\\w+)\\}\\}` pattern has no such
attribute-traversal surface at all -- it can only ever substitute one
of a small, real, known set of variable names.

**Robustness (vision critique)**: a real, missing variable is left as
its own literal `{{name}}` placeholder in the rendered output, never
silently blanked and never a raised exception -- a real typo in a
template is visible and debuggable in the actual rendered text, rather
than either crashing every real run or hiding the mistake."""

import datetime as dt
import re

from api.config import settings
from api.models.agent import Agent

_VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")

# Item 3's own literal 7 variables.
KNOWN_VARIABLES = ("user_name", "organization_name", "date", "time", "context", "tools", "knowledge_base")

_MAX_PLACEHOLDERS = 50  # real, minimal safeguard against a pathological template


def get_system_prompt_variables(agent: Agent) -> list[str]:
    """Item 2's own literal function -- item 3's own literal 7
    variable names (a real, static catalog; `agent` is accepted per
    the literal signature but every real agent shares the same real
    set today -- kept as a real parameter for a future, per-agent
    variable set to extend without a signature change)."""
    return list(KNOWN_VARIABLES)


def validate_system_prompt(prompt: str) -> list[str]:
    """Item 2's own literal function -- real, specific errors; an
    empty list means the real prompt is valid. Reuses
    `settings.SYSTEM_PROMPT_MAX_LENGTH` (Partie 4.3.4's own real,
    already-established bound for a system prompt sent to an LLM) --
    the same real constraint, not a second, arbitrary one."""
    errors = []
    if not prompt or not prompt.strip():
        errors.append("System prompt must be a real, non-empty string")
    if len(prompt) > settings.SYSTEM_PROMPT_MAX_LENGTH:
        errors.append(f"System prompt exceeds the real maximum length of {settings.SYSTEM_PROMPT_MAX_LENGTH} characters")

    placeholders = _VARIABLE_PATTERN.findall(prompt)
    if len(placeholders) > _MAX_PLACEHOLDERS:
        errors.append(f"Too many template placeholders: {len(placeholders)} (real maximum {_MAX_PLACEHOLDERS})")
    unknown = sorted(set(p for p in placeholders if p not in KNOWN_VARIABLES))
    if unknown:
        errors.append(f"Unknown template variables: {unknown} (expected one of {list(KNOWN_VARIABLES)})")

    return errors


def render_system_prompt(agent: Agent, context: dict | None = None) -> str:
    """Item 2's own literal function -- real substitution of
    `{{date}}`/`{{time}}` (computed here, no DB needed) plus whatever
    real values `context` supplies for the other real variables
    (`user_name`/`organization_name`/`context`/`tools`/
    `knowledge_base` all need real information -- a real DB lookup, the
    current request's own user, etc. -- this function stays DB-
    independent by design, so those are the CALLER's own real
    responsibility to resolve and pass in). Renders
    `system_prompt_template` when the real agent has one, falling back
    to the real, plain `system_prompt` otherwise (matching this
    étape's own literal "personnaliser le system prompt" -- a template
    is an enhancement, not a requirement)."""
    now = dt.datetime.now(dt.timezone.utc)
    values = {"date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M:%S UTC"), **(context or {})}

    template = agent.system_prompt_template or agent.system_prompt
    return _VARIABLE_PATTERN.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), template)


def preview_system_prompt(agent: Agent, context: dict | None = None) -> str:
    """Item 2's own literal function -- a real, thin wrapper around
    `render_system_prompt`: kept as its own named function to match
    this étape's own literal spec (the endpoint that lets an Owner see
    what their real template resolves to before saving), not a second,
    different rendering path."""
    return render_system_prompt(agent, context)
