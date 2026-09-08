"""Partie 8.1.19 -- Multi-langue UI (i18n)."""

from api.config import settings
from api.services.i18n import detect_user_language, get_all_translations, get_supported_languages, get_translation


def test_get_supported_languages_matches_config():
    assert get_supported_languages() == settings.UI_SUPPORTED_LANGUAGES


def test_get_translation_returns_real_value_for_each_language():
    """Validation criterion: les traductions fonctionnent."""
    for lang in get_supported_languages():
        value = get_translation(lang, "save")
        assert value and value != "save"


def test_get_translation_formats_params():
    assert get_translation("en", "welcome", {"name": "Ada"}) == "Welcome, Ada!"
    assert get_translation("fr", "welcome", {"name": "Ada"}) == "Bienvenue, Ada !"


def test_get_translation_falls_back_to_default_language():
    """Validation criterion: robustesse -- traduction manquante."""
    value = get_translation("xx", "save")
    assert value == get_translation(settings.UI_DEFAULT_LANGUAGE, "save")


def test_get_translation_falls_back_to_raw_key_when_missing_everywhere():
    assert get_translation("en", "this_key_does_not_exist") == "this_key_does_not_exist"


def test_get_all_translations_returns_full_dict():
    translations = get_all_translations("en")
    assert "save" in translations
    assert "cancel" in translations


def test_detect_user_language_prefers_cookie():
    assert detect_user_language("es-ES,es;q=0.9", cookie_value="fr") == "fr"


def test_detect_user_language_falls_back_to_accept_language_header():
    assert detect_user_language("de-DE,de;q=0.9,en;q=0.8") == "de"


def test_detect_user_language_falls_back_to_default():
    assert detect_user_language(None) == settings.UI_DEFAULT_LANGUAGE
    assert detect_user_language("zz-ZZ") == settings.UI_DEFAULT_LANGUAGE


async def test_i18n_endpoints(client):
    languages = await client.get("/i18n/languages")
    assert languages.status_code == 200
    assert "fr" in languages.json()["languages"]

    translations = await client.get("/i18n/translations/fr")
    assert translations.status_code == 200
    assert translations.json()["save"] == "Enregistrer"

    unsupported = await client.get("/i18n/translations/xx")
    assert unsupported.status_code == 404

    set_lang = await client.post("/i18n/language", json={"language": "es"})
    assert set_lang.status_code == 200
    assert "lang=es" in set_lang.headers.get("set-cookie", "")
