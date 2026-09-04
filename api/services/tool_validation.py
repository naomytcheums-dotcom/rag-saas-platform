"""
Partie 5.1.9 -- validating a tool's real result against a real,
JSON-schema-shaped contract before an agent uses it.

**A real, hand-written validator, not the `jsonschema` package** (which
happens to be importable transitively in this environment, but is not
a declared direct dependency anywhere in requirements.txt/
requirements-api.txt/pyproject.toml) -- relying on an undeclared,
transitive package would be fragile (it could disappear the moment an
unrelated dependency drops it). The real subset implemented here
(`type`/`required`/`properties`/`minimum`/`maximum`/`minLength`/
`maxLength`) covers everything `TOOL_VALIDATION_SCHEMAS` below actually
needs; a heavier subset of JSON Schema can be added for real, future
need.

**`TOOL_VALIDATION_SCHEMAS`, a real, mutable, in-process registry**
(same shape as `api.services.tools`'s own `_REGISTRY`, not stuffed into
`api.config.settings` -- a dict of dicts has no sane single-value
config shape) -- pre-populated with a real schema for the one real tool
whose result shape is worth constraining today (`calculator`, a numeric
string). `search_result_schema`/`database_result_schema`/
`http_result_schema` (this étape's own literal names) are shipped as
real, standalone, exported constants -- honestly NOT yet attached to
any `tool_name` in the registry, since no search/database/HTTP tool is
registered in `api.services.tools` yet (that's Partie 5.2's own,
larger, separate scope); they are real, ready-to-use schemas for
whenever such a tool exists."""

from typing import Any

from api.config import settings

_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str, "boolean": bool, "array": list, "object": dict, "null": type(None),
}


def validate_type(result: Any, expected_type: str) -> bool:
    """Partie 5.1.9's own literal function."""
    if expected_type == "integer":
        return isinstance(result, int) and not isinstance(result, bool)
    if expected_type == "number":
        return isinstance(result, (int, float)) and not isinstance(result, bool)
    if expected_type not in _TYPE_MAP:
        raise ValueError(f"Unknown schema type: {expected_type!r}")
    return isinstance(result, _TYPE_MAP[expected_type])


def validate_range(result: Any, min_val: float | None = None, max_val: float | None = None) -> bool:
    """Partie 5.1.9's own literal function."""
    if not isinstance(result, (int, float)) or isinstance(result, bool):
        return False
    if min_val is not None and result < min_val:
        return False
    if max_val is not None and result > max_val:
        return False
    return True


def validate_required_fields(result: Any, required_fields: list[str]) -> bool:
    """Partie 5.1.9's own literal function."""
    return isinstance(result, dict) and all(field in result for field in required_fields)


def get_validation_errors(result: Any, schema: dict) -> list[str]:
    """Partie 5.1.9's own literal function -- every real, human-readable
    reason `result` fails `schema`; an empty list means it's valid."""
    errors: list[str] = []
    expected_type = schema.get("type")

    if expected_type is not None and not validate_type(result, expected_type):
        errors.append(f"Expected type {expected_type!r}, got {type(result).__name__!r}")
        return errors  # further checks below assume the top-level type already matched

    if expected_type == "object" and isinstance(result, dict):
        required = schema.get("required", [])
        if not validate_required_fields(result, required):
            missing = [f for f in required if f not in result]
            errors.append(f"Missing required fields: {missing}")
        for field, field_schema in schema.get("properties", {}).items():
            if field in result:
                errors.extend(f"{field}: {e}" for e in get_validation_errors(result[field], field_schema))

    if expected_type in ("integer", "number"):
        if not validate_range(result, schema.get("minimum"), schema.get("maximum")):
            errors.append(f"Value {result!r} is outside the real bounds [{schema.get('minimum')}, {schema.get('maximum')}]")

    if expected_type == "string":
        min_length, max_length = schema.get("minLength"), schema.get("maxLength")
        if min_length is not None and len(result) < min_length:
            errors.append(f"String too short: {len(result)} < {min_length}")
        if max_length is not None and len(result) > max_length:
            errors.append(f"String too long: {len(result)} > {max_length}")

    return errors


def validate_schema(result: Any, schema: dict) -> bool:
    """Partie 5.1.9's own literal function."""
    return not get_validation_errors(result, schema)


# ------------------------------------- Partie 5.1.9's own literal schemas -------------------------------------

CALCULATION_RESULT_SCHEMA = {"type": "string", "minLength": 1}
SEARCH_RESULT_SCHEMA = {
    "type": "object", "required": ["results"],
    "properties": {"results": {"type": "array"}, "total": {"type": "integer", "minimum": 0}},
}
DATABASE_RESULT_SCHEMA = {"type": "object", "required": ["rows"], "properties": {"rows": {"type": "array"}}}
HTTP_RESULT_SCHEMA = {
    "type": "object", "required": ["status_code"],
    "properties": {"status_code": {"type": "integer", "minimum": 100, "maximum": 599}, "body": {"type": "string"}},
}

_SCHEMAS: dict[str, dict] = {"calculator": CALCULATION_RESULT_SCHEMA}


def register_tool_schema(tool_name: str, schema: dict) -> None:
    """Real, additional function (not literally named by this étape) --
    how a future real tool registers its own result contract, the same
    `register_*`-into-a-module-level-dict pattern already used by
    `api.services.tools.register_tool`."""
    _SCHEMAS[tool_name] = schema


def validate_tool_result(tool_name: str, result: Any) -> bool:
    """Partie 5.1.9's own literal function.

    **Robustness (vision critique)**: `TOOL_VALIDATION_ENABLED=False`
    always passes (`True`), no matter what. A tool with NO registered
    schema passes in the real, default (non-strict) mode -- nothing to
    check it against -- but FAILS in strict mode
    (`TOOL_VALIDATION_STRICT=True`), which treats "no declared result
    contract" itself as a real validation failure."""
    if not settings.TOOL_VALIDATION_ENABLED:
        return True

    schema = _SCHEMAS.get(tool_name)
    if schema is None:
        return not settings.TOOL_VALIDATION_STRICT
    return validate_schema(result, schema)
