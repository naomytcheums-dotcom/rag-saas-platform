"""Partie 5.1.9 -- tool result validation. Pure functions, no DB, no
mocking."""

from api.services.tool_validation import (
    CALCULATION_RESULT_SCHEMA, DATABASE_RESULT_SCHEMA, HTTP_RESULT_SCHEMA, SEARCH_RESULT_SCHEMA,
    get_validation_errors, register_tool_schema, validate_range, validate_required_fields, validate_schema,
    validate_tool_result, validate_type,
)


# --------------------------------------- validate_type --


def test_validate_type_accepts_a_matching_string():
    assert validate_type("hello", "string") is True


def test_validate_type_rejects_a_mismatched_type():
    assert validate_type(42, "string") is False


def test_validate_type_distinguishes_integer_from_boolean():
    """A real, common JSON-schema gotcha: bool is a subclass of int in
    Python -- must not be silently accepted as an integer."""
    assert validate_type(True, "integer") is False
    assert validate_type(1, "integer") is True


def test_validate_type_raises_for_an_unknown_type():
    import pytest
    with pytest.raises(ValueError):
        validate_type("x", "not-a-real-type")


# --------------------------------------- validate_range --


def test_validate_range_accepts_a_value_within_bounds():
    assert validate_range(50, min_val=0, max_val=100) is True


def test_validate_range_rejects_a_value_outside_bounds():
    assert validate_range(150, min_val=0, max_val=100) is False


def test_validate_range_rejects_a_non_numeric_value():
    assert validate_range("not a number", min_val=0, max_val=100) is False


# --------------------------------------- validate_required_fields --


def test_validate_required_fields_accepts_a_complete_dict():
    assert validate_required_fields({"a": 1, "b": 2}, ["a", "b"]) is True


def test_validate_required_fields_rejects_a_missing_field():
    assert validate_required_fields({"a": 1}, ["a", "b"]) is False


# --------------------------------------- get_validation_errors / validate_schema --


def test_validate_schema_accepts_a_real_matching_object():
    schema = {"type": "object", "required": ["results"], "properties": {"total": {"type": "integer", "minimum": 0}}}
    assert validate_schema({"results": [], "total": 3}, schema) is True


def test_get_validation_errors_reports_a_real_missing_field():
    schema = {"type": "object", "required": ["rows"]}
    errors = get_validation_errors({}, schema)
    assert any("rows" in e for e in errors)


def test_get_validation_errors_reports_a_real_type_mismatch():
    errors = get_validation_errors("not an int", {"type": "integer"})
    assert errors


def test_get_validation_errors_validates_nested_properties():
    schema = {"type": "object", "properties": {"status_code": {"type": "integer", "minimum": 100, "maximum": 599}}}
    errors = get_validation_errors({"status_code": 999}, schema)
    assert any("status_code" in e for e in errors)


# --------------------------------------- named schemas --


def test_named_schemas_are_real_and_usable():
    assert validate_schema("42", CALCULATION_RESULT_SCHEMA) is True
    assert validate_schema({"results": []}, SEARCH_RESULT_SCHEMA) is True
    assert validate_schema({"rows": []}, DATABASE_RESULT_SCHEMA) is True
    assert validate_schema({"status_code": 200}, HTTP_RESULT_SCHEMA) is True


# --------------------------------------- validate_tool_result --


def test_validate_tool_result_uses_the_real_registered_schema():
    """Validation criterion: la validation fonctionne."""
    assert validate_tool_result("calculator", "14") is True
    assert validate_tool_result("calculator", 14) is False  # calculator's real handler always returns a str


def test_validate_tool_result_passes_an_unregistered_tool_in_non_strict_mode(monkeypatch):
    from api.config import settings
    monkeypatch.setattr(settings, "TOOL_VALIDATION_STRICT", False)
    assert validate_tool_result("never-registered", "anything") is True


def test_validate_tool_result_fails_an_unregistered_tool_in_strict_mode(monkeypatch):
    """Validation criterion: les modes strict/non-strict fonctionnent."""
    from api.config import settings
    monkeypatch.setattr(settings, "TOOL_VALIDATION_STRICT", True)
    assert validate_tool_result("never-registered", "anything") is False


def test_validate_tool_result_always_passes_when_validation_disabled(monkeypatch):
    """Validation criterion: robustesse -- que se passe-t-il si un
    résultat est invalide (avec la validation désactivée) ?"""
    from api.config import settings
    monkeypatch.setattr(settings, "TOOL_VALIDATION_ENABLED", False)
    assert validate_tool_result("calculator", 12345) is True  # would fail schema if enabled


def test_register_tool_schema_adds_a_real_new_schema():
    register_tool_schema("test-only-tool", {"type": "boolean"})
    assert validate_tool_result("test-only-tool", True) is True
    assert validate_tool_result("test-only-tool", "not a bool") is False
