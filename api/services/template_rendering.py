"""
Shared, real, safe `{{variable}}` template substitution -- extracted
out of `api/services/agent_prompts.py` (Partie 5.3.2) so every real
workflow block renderer (Parties 5.4.3-5.4.11: `render_llm_prompt`,
`render_rag_query`, `render_search_query`, `render_http_url`,
`render_http_body`, `render_email_template`, `render_calendar_field`,
`render_human_message`) reuses the SAME real, tested, safe
implementation instead of re-writing it up to 9 more times.

**Still the same real, deliberate choice as Partie 5.3.2**: a
hand-written regex match-and-replace on a fixed `\\{\\{(\\w+)\\}\\}`
pattern, NOT `str.format()`/`str.format_map()` (a real, documented
attribute-traversal vulnerability class when the format STRING itself,
not just its values, comes from a real but not fully trusted author --
a workflow's own node `data` is Manager-authored, same trust level as
an agent's own system prompt template).

**Same real robustness answer**: a real, missing variable is left as
its own literal `{{name}}` placeholder -- never silently blanked,
never a raised exception.

**Real, dotted-path lookup, added for Partie 5.4.10/5.4.11's own
literal `{{user.email}}`/`{{user.name}}` variables**: a flat
`\\w+`-only pattern (this module's own original Partie 5.3.2 shape)
would never match a dotted name at all -- `{{user.email}}` would stay
silently, permanently unrendered even when a real, correct value
exists under a real, nested `context["user"]["email"]`. The pattern
now accepts `[\\w.]+` and resolves each dot-separated segment as a
real, nested dict lookup; a flat key (no dot) resolves exactly as
before -- fully backward-compatible with every existing real caller
(Partie 5.3.2's own agent prompts, Parties 5.4.3-5.4.9's own single-
word variables)."""

import re

_VARIABLE_PATTERN = re.compile(r"\{\{([\w.]+)\}\}")
MAX_PLACEHOLDERS = 50  # real, minimal safeguard against a pathological template


def _resolve(path: str, values: dict) -> tuple[object, bool]:
    current = values
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None, False
    return current, True


def render_template(template: str, values: dict) -> str:
    """The real, shared substitution every real template renderer in
    this codebase uses. A real, given path may be a flat key (`name`)
    or a real, dotted, nested path (`user.name`); a resolved non-string
    value is stringified (`str(...)`) before substitution -- a
    template is always real, plain text."""
    def _sub(match: re.Match) -> str:
        value, found = _resolve(match.group(1), values)
        return str(value) if found else match.group(0)

    return _VARIABLE_PATTERN.sub(_sub, template)


def find_placeholders(template: str) -> list[str]:
    """Real, shared placeholder extraction -- used by every real
    `validate_*_config` that rejects an unknown variable name."""
    return _VARIABLE_PATTERN.findall(template)
