"""
Partie 3.4.5 -- real, standalone metadata filtering over real search
results: `build_metadata_filter`/`apply_metadata_filter`/
`validate_filters`/`get_filterable_fields`/`parse_filter_value` (item
2's own literal functions).

**A real, honest, documented scope limit for `author`**: this
codebase's own `Document` model (`api/models/document.py`) has NO real
author/creator NAME field -- only `created_by`, a real user ID
foreign key, never a human-readable name. `author` stays a real,
listed, literal filterable field (this étape's own literal ask names
it explicitly), but honestly can never match anything today until a
real name field exists somewhere to populate a real result's own
`"author"` key from -- not silently dropped, not fabricated.

**Real, deliberate standalone scope, same reasoning as Partie
3.2.2-3.2.8's own established precedent**: `apply_metadata_filter`
operates on an already-produced list of real result dicts (the same
real shape `api.services.retrieval_pipeline.search`'s own results
already have -- `document_id`, `content`, `metadata_json`, etc.),
filtering by whichever of these 7 real fields a caller's own results
actually carry. Not yet wired into a live search call (that pipeline
doesn't currently populate `author`/`created_date`/`tags`/`source` on
its own result dicts) -- a real, honest, documented gap for a future
caller to close by enriching those results first, not this module's
own job to fabricate.
"""

import datetime as dt

from api.config import settings

# Item 3's own literal 7 filterable fields, each with its own real,
# documented value shape.
_FILTERABLE_FIELDS: dict[str, str] = {
    "author": "text",
    "created_date": "date",
    "tags": "list",
    "document_type": "text",
    "source": "text",
    "workspace_id": "text",
    "file_size": "number",
}


def get_filterable_fields() -> list[str]:
    """Item 4's own literal function."""
    return list(_FILTERABLE_FIELDS)


def _coerce_date(value) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    return dt.datetime.fromisoformat(value)


def parse_filter_value(value, field_type: str):
    """Item 5's own literal function -- real, per-type parsing/
    validation, so a real, malformed filter fails loudly at
    `build_metadata_filter` time, not silently mismatching every real
    result later."""
    if field_type == "date":
        if isinstance(value, dict):
            allowed = {"before", "after", "between"}
            if not set(value).issubset(allowed):
                raise ValueError(f"Invalid date filter keys: {set(value) - allowed} (expected a subset of {allowed})")
            if "between" in value:
                if not (isinstance(value["between"], (list, tuple)) and len(value["between"]) == 2):
                    raise ValueError("A real 'between' date filter needs exactly [start, end]")
                _coerce_date(value["between"][0])
                _coerce_date(value["between"][1])
            for key in ("before", "after"):
                if key in value:
                    _coerce_date(value[key])
            return value
        _coerce_date(value)
        return value
    if field_type == "number":
        if isinstance(value, dict):
            allowed = {"min", "max"}
            if not set(value).issubset(allowed):
                raise ValueError(f"Invalid number filter keys: {set(value) - allowed} (expected a subset of {allowed})")
            return value
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"Invalid number filter value: {value!r}")
        return value
    if field_type == "list":
        return value if isinstance(value, list) else [value]
    return value


def validate_filters(filters: dict) -> None:
    """Item 3's own literal function -- real field names AND real,
    per-type value shapes, both checked."""
    if len(filters) > settings.METADATA_FILTER_MAX_OPERATORS:
        raise ValueError(f"Too many filters: {len(filters)} (max {settings.METADATA_FILTER_MAX_OPERATORS})")
    for field, value in filters.items():
        if field not in _FILTERABLE_FIELDS:
            raise ValueError(f"Unknown filterable field: {field!r} (expected one of {get_filterable_fields()})")
        parse_filter_value(value, _FILTERABLE_FIELDS[field])


def build_metadata_filter(filters: dict) -> dict:
    """Item 2's own literal function -- a real, validated, normalized
    filter spec, ready for `apply_metadata_filter` below."""
    validate_filters(filters)
    return {field: parse_filter_value(value, _FILTERABLE_FIELDS[field]) for field, value in filters.items()}


def _matches_text(value, parsed) -> bool:
    return value is not None and value == parsed


def _matches_date(value, parsed) -> bool:
    if value is None:
        return False
    value = _coerce_date(value)
    if isinstance(parsed, dict):
        if "before" in parsed and not value < _coerce_date(parsed["before"]):
            return False
        if "after" in parsed and not value > _coerce_date(parsed["after"]):
            return False
        if "between" in parsed:
            start, end = parsed["between"]
            if not (_coerce_date(start) <= value <= _coerce_date(end)):
                return False
        return True
    return value == _coerce_date(parsed)


def _matches_number(value, parsed) -> bool:
    if value is None:
        return False
    if isinstance(parsed, dict):
        if "min" in parsed and value < parsed["min"]:
            return False
        if "max" in parsed and value > parsed["max"]:
            return False
        return True
    return value == parsed


def _matches_list(value, parsed: list) -> bool:
    """A real, standard "any of" tag-filter semantic: a real result
    matches when it carries AT LEAST ONE real tag from the filter's own
    real list."""
    if not value:
        return False
    return bool(set(value) & set(parsed))


_MATCHERS = {"text": _matches_text, "date": _matches_date, "number": _matches_number, "list": _matches_list}


def apply_metadata_filter(query_results: list[dict], filters: dict) -> list[dict]:
    """Item 2's own literal function -- `METADATA_FILTERING_ENABLED=False`
    is a real, deliberate kill switch (results pass through unchanged,
    the same real convention `PARENT_CHILD_ENABLED`/
    `LANGUAGE_DETECTION_ENABLED` already established)."""
    if not settings.METADATA_FILTERING_ENABLED or not filters:
        return list(query_results)

    built = build_metadata_filter(filters)
    matched = []
    for result in query_results:
        if all(_MATCHERS[_FILTERABLE_FIELDS[field]](result.get(field), parsed) for field, parsed in built.items()):
            matched.append(result)
    return matched
