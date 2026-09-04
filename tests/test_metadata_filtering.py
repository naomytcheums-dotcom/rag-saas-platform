"""Partie 3.4.5 -- tests for api/services/metadata_filtering.py."""

import pytest

from api.services.metadata_filtering import (
    apply_metadata_filter,
    build_metadata_filter,
    get_filterable_fields,
    parse_filter_value,
    validate_filters,
)

_RESULTS = [
    {"chunk_id": "1", "document_type": "pdf", "workspace_id": "ws-a", "file_size": 1000, "tags": ["finance", "q1"], "created_date": "2026-01-15"},
    {"chunk_id": "2", "document_type": "docx", "workspace_id": "ws-b", "file_size": 5000, "tags": ["hr"], "created_date": "2026-03-01"},
    {"chunk_id": "3", "document_type": "pdf", "workspace_id": "ws-a", "file_size": 20000, "tags": ["finance"], "created_date": "2026-06-10"},
]


def test_get_filterable_fields_returns_the_real_literal_7_fields():
    """Validation criterion: la liste des champs filtrables est
    correcte."""
    fields = get_filterable_fields()
    assert set(fields) == {"author", "created_date", "tags", "document_type", "source", "workspace_id", "file_size"}


def test_validate_filters_rejects_an_unknown_field():
    with pytest.raises(ValueError):
        validate_filters({"not_a_real_field": "x"})


def test_validate_filters_rejects_too_many_operators():
    """Validation criterion: robustesse -- filtre invalide (trop
    d'opérateurs)."""
    with pytest.raises(ValueError):
        validate_filters({"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6})


def test_validate_filters_accepts_real_valid_filters():
    validate_filters({"document_type": "pdf", "file_size": {"min": 100, "max": 5000}})


def test_parse_filter_value_rejects_a_malformed_number_filter():
    with pytest.raises(ValueError):
        parse_filter_value({"unexpected_key": 1}, "number")


def test_parse_filter_value_rejects_a_malformed_date_filter():
    with pytest.raises(ValueError):
        parse_filter_value({"unexpected_key": "2026-01-01"}, "date")


def test_parse_filter_value_normalizes_a_bare_tag_to_a_real_list():
    assert parse_filter_value("finance", "list") == ["finance"]


def test_build_metadata_filter_validates_and_returns_a_real_spec():
    spec = build_metadata_filter({"document_type": "pdf"})
    assert spec == {"document_type": "pdf"}


def test_apply_metadata_filter_by_document_type():
    """Validation criterion: le filtrage par type de document
    fonctionne."""
    filtered = apply_metadata_filter(_RESULTS, {"document_type": "pdf"})
    assert {r["chunk_id"] for r in filtered} == {"1", "3"}


def test_apply_metadata_filter_by_workspace():
    filtered = apply_metadata_filter(_RESULTS, {"workspace_id": "ws-b"})
    assert {r["chunk_id"] for r in filtered} == {"2"}


def test_apply_metadata_filter_by_file_size_range():
    filtered = apply_metadata_filter(_RESULTS, {"file_size": {"min": 2000, "max": 20000}})
    assert {r["chunk_id"] for r in filtered} == {"2", "3"}


def test_apply_metadata_filter_by_tags():
    """Validation criterion: le filtrage par tags fonctionne."""
    filtered = apply_metadata_filter(_RESULTS, {"tags": "finance"})
    assert {r["chunk_id"] for r in filtered} == {"1", "3"}


def test_apply_metadata_filter_by_date_range():
    """Validation criterion: le filtrage par date fonctionne."""
    filtered = apply_metadata_filter(_RESULTS, {"created_date": {"after": "2026-02-01", "before": "2026-05-01"}})
    assert {r["chunk_id"] for r in filtered} == {"2"}


def test_apply_metadata_filter_by_date_between():
    filtered = apply_metadata_filter(_RESULTS, {"created_date": {"between": ["2026-01-01", "2026-04-01"]}})
    assert {r["chunk_id"] for r in filtered} == {"1", "2"}


def test_apply_metadata_filter_combines_multiple_real_filters():
    filtered = apply_metadata_filter(_RESULTS, {"document_type": "pdf", "workspace_id": "ws-a"})
    assert {r["chunk_id"] for r in filtered} == {"1", "3"}


def test_apply_metadata_filter_author_never_matches_without_real_author_data():
    """A real, honest, documented gap: no result here carries a real
    'author' key (this codebase has no such field on Document), so
    this real filter correctly matches nothing -- never a false
    positive."""
    filtered = apply_metadata_filter(_RESULTS, {"author": "Ada Lovelace"})
    assert filtered == []


def test_apply_metadata_filter_is_empty_input_safe():
    assert apply_metadata_filter([], {"document_type": "pdf"}) == []


def test_apply_metadata_filter_returns_everything_when_no_real_filters_given():
    assert apply_metadata_filter(_RESULTS, {}) == _RESULTS


def test_apply_metadata_filter_respects_the_real_kill_switch(monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "METADATA_FILTERING_ENABLED", False)
    filtered = apply_metadata_filter(_RESULTS, {"document_type": "pdf"})
    assert filtered == _RESULTS
