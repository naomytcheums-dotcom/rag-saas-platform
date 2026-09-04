"""Partie 3.1.7 -- tests for api/services/language_detection.py."""

from unittest.mock import patch

from api.config import settings
from api.services.language_detection import (
    detect_language,
    detect_language_batch,
    get_language_confidence,
    get_supported_languages,
    set_language_fallback,
)

_FRENCH = "Bonjour, comment allez-vous aujourd'hui ? Il fait très beau à Paris en ce moment."
_ENGLISH = "Hello, how are you doing today? The weather is very nice in London right now."


def test_detect_language_works_for_french():
    """Validation criterion: la détection fonctionne pour le français."""
    assert detect_language(_FRENCH) == "fr"


def test_detect_language_works_for_english():
    """Validation criterion: la détection fonctionne pour l'anglais."""
    assert detect_language(_ENGLISH) == "en"


def test_detect_language_returns_a_real_best_guess_for_mixed_text():
    """Validation criterion: un texte mixte ne fait jamais planter la
    détection -- langdetect renvoie sa propre meilleure estimation
    unique, pas un échec."""
    mixed = _FRENCH + " " + _ENGLISH
    result = detect_language(mixed)
    assert result in {"fr", "en"}


def test_detect_language_fails_gracefully_for_text_too_short():
    """Validation criterion / vision critique 3 -- la détection échoue
    gracieusement pour un texte trop court (jamais une exception)."""
    assert detect_language("hi") == settings.LANGUAGE_DETECTION_FALLBACK


def test_detect_language_fails_gracefully_for_none_or_empty():
    assert detect_language(None) == settings.LANGUAGE_DETECTION_FALLBACK
    assert detect_language("") == settings.LANGUAGE_DETECTION_FALLBACK
    assert detect_language("   ") == settings.LANGUAGE_DETECTION_FALLBACK


def test_detect_language_respects_a_custom_fallback():
    assert detect_language("x", fallback="es") == "es"


def test_detect_language_respects_the_disabled_kill_switch():
    with patch.object(settings, "LANGUAGE_DETECTION_ENABLED", False):
        assert detect_language(_FRENCH) == settings.LANGUAGE_DETECTION_FALLBACK


def test_detect_language_is_deterministic_across_calls():
    """langdetect's own classifier is non-deterministic unless seeded --
    confirms the real, module-level seed actually took effect."""
    results = {detect_language(_FRENCH) for _ in range(20)}
    assert results == {"fr"}


def test_detect_language_batch_detects_each_real_text_independently():
    assert detect_language_batch([_FRENCH, _ENGLISH]) == ["fr", "en"]


def test_get_language_confidence_returns_a_real_probability_distribution():
    confidence = get_language_confidence(_FRENCH)
    assert "fr" in confidence
    assert 0.0 < confidence["fr"] <= 1.0


def test_get_language_confidence_is_empty_for_text_too_short():
    assert get_language_confidence("hi") == {}
    assert get_language_confidence(None) == {}


def test_get_supported_languages_returns_a_real_fixed_list():
    languages = get_supported_languages()
    assert "fr" in languages
    assert "en" in languages
    assert len(languages) >= 50


def test_set_language_fallback_overrides_for_inconclusive_text():
    assert set_language_fallback("hi", fallback="de") == "de"
    assert set_language_fallback(_FRENCH, fallback="de") == "fr"  # a real detection still wins over the override
