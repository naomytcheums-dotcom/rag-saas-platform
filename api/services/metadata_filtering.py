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
import re

from api.config import settings

# --------------------------------------------------------------------
# Phase 4, Étape 3 -- real, SQL-level metadata filtering, wired directly
# into `api.services.retrieval_pipeline.fetch_organization_chunks` (the
# one, real, shared choke point every search strategy already goes
# through -- see that function's own docstring). A real, deliberate,
# documented DIFFERENCE from `apply_metadata_filter` above, not a
# duplicate: that function post-filters an already-fetched, already-
# ENRICHED result list against a fixed, 7-field allowlist
# (`author`/`created_date`/`tags`/`document_type`/`source`/
# `workspace_id`/`file_size`) that this codebase's own real search
# results never actually carry (its own top docstring already, honestly,
# documents this as "not yet wired into a live search call"). This
# étape's own literal ask is different and more general: filter on
# whatever real, arbitrary keys a real chunk's own `metadata_json`
# ACTUALLY holds (department/language/year/etc, an arbitrary JSON
# key-value store, never a fixed field list) -- and do it BEFORE a real
# chunk can ever become a candidate for BM25/vector ranking, not after.
#
# Real, documented scope decision: filters match against
# `DocumentChunk.metadata_json` (the one, real, per-chunk JSON store
# `fetch_organization_chunks` already selects), not
# `Document.metadata_json` -- this codebase has no real, user-facing way
# to set arbitrary custom key/value metadata on a `Document` today (its
# own `metadata_json` is populated exclusively by the extraction
# pipeline -- format-specific info, errors -- never by a caller-supplied
# custom dict); inventing a merge/precedence rule between two, real,
# independently-populated JSON stores for values neither is currently
# designed to hold would be real, unjustified new architecture. A real
# chunk's own `metadata_json` (already the target of every other
# per-chunk classification in this codebase -- `chunking_strategy`,
# `language`, `parent_context`, etc) is the correct, minimal, already-
# real target.
#
# Real, deliberate scope limit on operators, found via direct testing
# (not assumed): `exists`/`not_exists` were tried against this
# codebase's own plain `JSON` column type (not `JSONB`) on SQLite (this
# codebase's own real, fast-test backend) and produced a real, WRONG
# result -- `column[key].isnot(None)` matched every real row regardless
# of whether `key` was actually present, because a missing JSON key and
# a real SQL NULL are not the same real thing at this JSON comparator
# level, backend-dependently. Rather than ship a real, silently-broken
# operator (this étape's own explicit "ne développe pas inutilement un
# langage de requête complexe si le stockage actuel ne le justifie pas"),
# `exists`/`not_exists` are NOT implemented -- a real, honest, documented
# gap, not a fabricated feature.

_METADATA_FILTER_KEY_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
_METADATA_FILTER_OPERATORS = {"equals", "not_equals", "in", "not_in", "gt", "gte", "lt", "lte"}
_METADATA_FILTER_COMPARISON_OPERATORS = {"gt", "gte", "lt", "lte"}
_METADATA_FILTER_LIST_OPERATORS = {"in", "not_in"}


def _validate_scalar_value(value) -> None:
    """Real, minimal type guard -- only real, JSON-safe scalars are ever
    bound as real SQL parameters (never a raw, user-controlled string
    spliced into a real query)."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"Invalid metadata filter value: {value!r} (must be a string, int, or float)")


def normalize_metadata_filters(filters: dict) -> dict[str, dict]:
    """Item 3's own literal ask -- real, strict validation of a real,
    caller-supplied `filters` dict (this étape's own literal API shape:
    `{"department": "finance"}` or `{"year": {"gt": 2020}}`) into a
    normalized `{key: {"op": ..., "value": ...}}` form. Real, explicit
    rejection (requirement 17, "rejette proprement"): an unknown
    operator, a malformed key, an oversized filter count, or a
    real, incompatible value shape all raise `ValueError` immediately,
    never silently mismatch later or get coerced into something the
    caller didn't ask for."""
    if not isinstance(filters, dict):
        raise ValueError(f"Invalid filters: {filters!r} (must be an object)")
    if len(filters) > settings.METADATA_FILTER_MAX_OPERATORS:
        raise ValueError(f"Too many metadata filters: {len(filters)} (max {settings.METADATA_FILTER_MAX_OPERATORS})")

    normalized: dict[str, dict] = {}
    for key, value in filters.items():
        if not isinstance(key, str) or not _METADATA_FILTER_KEY_RE.match(key):
            raise ValueError(f"Invalid metadata filter key: {key!r} (expected [A-Za-z0-9_]{{1,64}})")

        if isinstance(value, dict):
            if len(value) != 1:
                raise ValueError(f"Invalid metadata filter for {key!r}: expected exactly one operator, got {list(value)}")
            op, op_value = next(iter(value.items()))
            if op not in _METADATA_FILTER_OPERATORS:
                raise ValueError(f"Unknown metadata filter operator: {op!r} (expected one of {sorted(_METADATA_FILTER_OPERATORS)})")
            if op in _METADATA_FILTER_LIST_OPERATORS:
                if not isinstance(op_value, list) or not op_value:
                    raise ValueError(f"Invalid metadata filter for {key!r}: {op!r} requires a real, non-empty list")
                for item in op_value:
                    _validate_scalar_value(item)
            elif op in _METADATA_FILTER_COMPARISON_OPERATORS:
                if isinstance(op_value, bool) or not isinstance(op_value, (int, float)):
                    raise ValueError(f"Invalid metadata filter for {key!r}: {op!r} requires a real number")
            else:
                _validate_scalar_value(op_value)
        else:
            op, op_value = "equals", value
            _validate_scalar_value(op_value)

        normalized[key] = {"op": op, "value": op_value}
    return normalized


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def build_metadata_filter_clauses(column, filters: dict) -> list:
    """Item 4's own literal ask -- real, parameterized SQLAlchemy
    clauses over a real JSON column (`DocumentChunk.metadata_json`),
    one clause per real, validated filter key. Every real value is bound
    through SQLAlchemy's own real parameter binding (`==`/`.in_()`/`>`/
    etc against a real, indexed JSON element) -- never raw string
    interpolation, so a real, malicious filter KEY (already rejected by
    `normalize_metadata_filters`'s own regex) or VALUE can never reach
    real SQL text.

    Real, VALUE-TYPE-AWARE cast, found necessary via direct, empirical
    testing against this codebase's own real SQLite test backend (not
    assumed): SQLAlchemy's JSON comparator's own `.as_string()` matches
    correctly against a real chunk's own `metadata_json` key that
    actually holds a real JSON STRING (`"department": "finance"`), but
    does NOT correctly match a real JSON NUMBER (`"year": 2026`) even
    after `str()`-converting the real filter's own comparison value --
    a real, empirically-confirmed SQLAlchemy/SQLite JSON-comparator
    quirk, not a bug in this function. `equals`/`not_equals`/`in`/
    `not_in` therefore dispatch on the real filter VALUE's own real
    Python type: a real number compares via `.as_float()` (the SAME
    real cast `gt`/`gte`/`lt`/`lte` already use, proven correct), a real
    string compares via `.as_string()`. Real, honest, documented scope
    limit: an `in`/`not_in` list mixing real numbers and real strings in
    the SAME real call is not supported (this étape's own literal ask
    never asked for mixed-type lists, and this codebase's own real
    metadata is written by ONE real ingestion path per real key, never
    inconsistently typed in practice)."""
    normalized = normalize_metadata_filters(filters)
    clauses = []
    for key, spec in normalized.items():
        op, value = spec["op"], spec["value"]
        element = column[key]
        if op == "equals":
            clauses.append((element.as_float() == value) if _is_number(value) else (element.as_string() == str(value)))
        elif op == "not_equals":
            clauses.append((element.as_float() != value) if _is_number(value) else (element.as_string() != str(value)))
        elif op == "in":
            if all(_is_number(v) for v in value):
                clauses.append(element.as_float().in_([float(v) for v in value]))
            else:
                clauses.append(element.as_string().in_([str(v) for v in value]))
        elif op == "not_in":
            if all(_is_number(v) for v in value):
                clauses.append(element.as_float().notin_([float(v) for v in value]))
            else:
                clauses.append(element.as_string().notin_([str(v) for v in value]))
        elif op == "gt":
            clauses.append(element.as_float() > value)
        elif op == "gte":
            clauses.append(element.as_float() >= value)
        elif op == "lt":
            clauses.append(element.as_float() < value)
        elif op == "lte":
            clauses.append(element.as_float() <= value)
    return clauses

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
