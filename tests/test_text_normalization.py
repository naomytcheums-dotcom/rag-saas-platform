"""Partie 3.1.2 -- tests for api/services/text_normalization.py."""

import pytest

from api.services.text_normalization import (
    normalize_accents,
    normalize_case,
    normalize_dates,
    normalize_numbers,
    normalize_text,
    normalize_units,
)


# ------------------------------------------------------------------ normalize_case --

def test_normalize_case_lowercases_by_default():
    """Validation criterion: la normalisation de casse fonctionne."""
    assert normalize_case("Hello WORLD") == "hello world"


def test_normalize_case_supports_upper_and_title():
    assert normalize_case("hello world", mode="upper") == "HELLO WORLD"
    assert normalize_case("hello world", mode="title") == "Hello World"


def test_normalize_case_rejects_an_unknown_mode():
    with pytest.raises(ValueError, match="mode"):
        normalize_case("x", mode="shout")


def test_normalize_case_handles_none_and_empty():
    """Vision critique 3: texte vide ou null."""
    assert normalize_case(None) == ""


# --------------------------------------------------------------- normalize_accents --

def test_normalize_accents_strips_real_french_accents():
    """Validation criterion: la normalisation des accents fonctionne."""
    assert normalize_accents("café élève naïve") == "cafe eleve naive"


def test_normalize_accents_keep_mode_is_a_real_no_op():
    assert normalize_accents("café", mode="keep") == "café"


def test_normalize_accents_handles_none_and_empty():
    assert normalize_accents(None) == ""


# ----------------------------------------------------------------- normalize_dates --

def test_normalize_dates_rewrites_dmy_to_iso_by_default():
    """Validation criterion: la normalisation des dates fonctionne."""
    assert normalize_dates("Le 15/03/2026 il a plu.") == "Le 2026-03-15 il a plu."


def test_normalize_dates_respects_mdy_order():
    """Vision critique 1: configurable par langue (ordre jour/mois)."""
    assert normalize_dates("On 03/15/2026 it rained.", date_order="mdy") == "On 2026-03-15 it rained."


def test_normalize_dates_leaves_an_invalid_date_alone():
    assert normalize_dates("40/15/2026") == "40/15/2026"


def test_normalize_dates_handles_none_and_empty():
    assert normalize_dates(None) == ""


# ---------------------------------------------------------------- normalize_numbers --

def test_normalize_numbers_removes_real_thousand_separators():
    """Validation criterion: la normalisation des nombres fonctionne."""
    assert normalize_numbers("1,000 units and 2 000 more") == "1000 units and 2000 more"


def test_normalize_numbers_leaves_a_real_decimal_comma_alone():
    """Un nombre décimal français ("3,14") n'est pas confondu avec un
    séparateur de milliers."""
    assert normalize_numbers("pi is about 3,14") == "pi is about 3,14"


def test_normalize_numbers_handles_none_and_empty():
    assert normalize_numbers(None) == ""


# ------------------------------------------------------------------ normalize_units --

def test_normalize_units_folds_case_variants():
    assert normalize_units("5 Kg of flour and 2 KM away") == "5 kg of flour and 2 km away"


def test_normalize_units_handles_none_and_empty():
    assert normalize_units(None) == ""


# -------------------------------------------------------------------- normalize_text --

def test_normalize_text_runs_the_real_default_pipeline():
    """Résultat des tests -- le pipeline complet fonctionne, avec des
    défauts conservateurs (pas de changement de casse ni d'accents)."""
    result = normalize_text("Le café coûte 1,000 Kg le 15/03/2026.")
    assert "café" in result  # accents kept by default
    assert "Le café" in result  # case kept by default
    assert "1000" in result
    assert "kg" in result
    assert "2026-03-15" in result


def test_normalize_text_can_opt_into_case_and_accent_changes():
    result = normalize_text("Café", case_mode="lower", accent_mode="remove")
    assert result == "cafe"


def test_normalize_text_handles_none_and_empty():
    """Vision critique 3: texte vide ou null."""
    assert normalize_text(None) == ""
    assert normalize_text("") == ""


def test_normalize_text_is_reasonably_fast_for_a_large_real_volume():
    """Vision critique 2: performance sur de gros volumes."""
    import time

    large_text = "Le prix est de 1,000 Kg le 15/03/2026 pour un total. " * 20000
    start = time.monotonic()
    result = normalize_text(large_text)
    elapsed = time.monotonic() - start

    assert elapsed < 5.0
    assert result
