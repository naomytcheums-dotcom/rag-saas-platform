"""Spec 10.2.7 -- toxicity filter (lexical, multilingual) and its opt-in wiring."""

import pytest

from api.services.toxicity_filter import detect_toxicity


@pytest.mark.parametrize("text", [
    "You are a stupid idiot", "this is fucking useless", "Tu es un connard", "eres un idiota", "du bist ein Arschloch", "voce e um babaca",
])
def test_insults_and_profanity_in_five_languages_are_flagged(text):
    result = detect_toxicity(text)
    assert result["is_toxic"] is True and result["categories"]


@pytest.mark.parametrize("text", ["I will kill you", "je vais te tuer", "te voy a matar", "ich bring dich um", "vou te matar"])
def test_threats_score_one(text):
    result = detect_toxicity(text)
    assert result["is_toxic"] and "threat" in result["categories"] and result["score"] == 1.0


@pytest.mark.parametrize("text", ["f.u.c.k", "FUUUUCK", "sh1t", "m3rde", "Cr\u00e9tin"])
def test_obfuscation_accents_and_repeated_letters_are_normalised(text):
    assert detect_toxicity(text)["is_toxic"] is True


@pytest.mark.parametrize("text", [
    "How do I kill a Python process?", "Please classify the assassin class in the game", "The scunthorpe problem: class, assess, Dickens",
    "Quel est le contrat de Madame Dupont ?", "", "   ",
])
def test_ordinary_text_and_substrings_are_not_flagged(text):
    assert detect_toxicity(text)["is_toxic"] is False


def test_matched_words_are_never_returned():
    result = detect_toxicity("you idiot")
    assert set(result) == {"is_toxic", "score", "categories"}
    assert "idiot" not in str(result)


def test_the_organization_setting_exists_and_defaults_to_off():
    from api.security.organization_settings import DEFAULT_SETTINGS

    assert DEFAULT_SETTINGS["toxicity_filter_enabled"] is False
