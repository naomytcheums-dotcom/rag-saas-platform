"""Partie 4.3.1-4.3.5 -- tests for api/services/llm_config.py's own
real, standalone LLM generation config resolvers."""

import pytest

from api.config import settings
from api.security.organization_settings import DEFAULT_SETTINGS
from api.services.llm_config import (
    resolve_llm_config,
    resolve_llm_model,
    resolve_llm_provider,
    resolve_max_tokens,
    resolve_system_prompt,
    resolve_temperature,
    resolve_top_p,
)

# ------------------------------- 4.3.1 provider / model -------------------------------


def test_resolve_llm_provider_falls_back_to_the_real_default():
    """Validation criterion: le fournisseur est lu depuis
    organization_settings, fallback fonctionne."""
    assert resolve_llm_provider() == DEFAULT_SETTINGS["llm_provider"]


def test_resolve_llm_provider_reads_from_real_organization_settings():
    assert resolve_llm_provider({"llm_provider": "openai"}) == "openai"


def test_resolve_llm_provider_override_wins():
    assert resolve_llm_provider({"llm_provider": "openai"}, override="mistral") == "mistral"


def test_resolve_llm_provider_rejects_an_unknown_provider():
    """Validation criterion: robustesse -- modèle/fournisseur non
    disponible."""
    with pytest.raises(ValueError):
        resolve_llm_provider(override="not-a-real-provider")


def test_resolve_llm_model_falls_back_to_the_real_providers_own_live_default():
    """Validation criterion: le modèle est lu, fallback fonctionne --
    a real, deliberate improvement over the stale table default."""
    model = resolve_llm_model({"llm_provider": "anthropic"})
    assert model == settings.ANTHROPIC_MODEL
    assert model != DEFAULT_SETTINGS["llm_model"]  # the real, known-stale table value


def test_resolve_llm_model_reads_from_real_organization_settings():
    assert resolve_llm_model({"llm_model": "claude-custom"}) == "claude-custom"


def test_resolve_llm_model_override_wins():
    assert resolve_llm_model({"llm_model": "claude-custom"}, override="claude-override") == "claude-override"


def test_resolve_llm_model_uses_the_real_resolved_providers_own_default():
    model = resolve_llm_model({"llm_provider": "openai"})
    assert model == settings.OPENAI_MODEL


# ------------------------------- 4.3.2 temperature -------------------------------


def test_resolve_temperature_falls_back_to_the_real_default():
    """Validation criterion: le fallback fonctionne."""
    assert resolve_temperature() == DEFAULT_SETTINGS["temperature"]


def test_resolve_temperature_reads_from_real_organization_settings():
    assert resolve_temperature({"temperature": 1.2}) == 1.2


def test_resolve_temperature_override_wins():
    assert resolve_temperature({"temperature": 1.2}, override=0.1) == 0.1


def test_resolve_temperature_rejects_out_of_range_values():
    """Validation criterion: robustesse -- valeur invalide."""
    with pytest.raises(ValueError):
        resolve_temperature(override=-0.1)
    with pytest.raises(ValueError):
        resolve_temperature(override=2.1)


def test_resolve_temperature_accepts_the_real_boundary_values():
    assert resolve_temperature(override=0.0) == 0.0
    assert resolve_temperature(override=2.0) == 2.0


# ------------------------------- 4.3.3 top_p -------------------------------


def test_resolve_top_p_falls_back_to_the_real_default():
    """Validation criterion: le fallback fonctionne."""
    assert resolve_top_p() == DEFAULT_SETTINGS["top_p"]


def test_resolve_top_p_reads_from_real_organization_settings():
    assert resolve_top_p({"top_p": 0.5}) == 0.5


def test_resolve_top_p_override_wins():
    assert resolve_top_p({"top_p": 0.5}, override=0.9) == 0.9


def test_resolve_top_p_rejects_out_of_range_values():
    """Validation criterion: robustesse -- valeur invalide."""
    with pytest.raises(ValueError):
        resolve_top_p(override=-0.1)
    with pytest.raises(ValueError):
        resolve_top_p(override=1.1)


# ------------------------------- 4.3.4 system prompt -------------------------------


def test_resolve_system_prompt_falls_back_to_the_real_default():
    """Validation criterion: le fallback fonctionne."""
    assert resolve_system_prompt() == DEFAULT_SETTINGS["system_prompt"]


def test_resolve_system_prompt_reads_from_real_organization_settings():
    assert resolve_system_prompt({"system_prompt": "Be concise."}) == "Be concise."


def test_resolve_system_prompt_override_wins():
    assert resolve_system_prompt({"system_prompt": "Be concise."}, override="Be verbose.") == "Be verbose."


def test_resolve_system_prompt_rejects_a_real_too_long_prompt():
    """Validation criterion: les prompts trop longs sont rejetés."""
    with pytest.raises(ValueError):
        resolve_system_prompt(override="x" * (settings.SYSTEM_PROMPT_MAX_LENGTH + 1))


def test_resolve_system_prompt_accepts_the_real_boundary_length():
    prompt = "x" * settings.SYSTEM_PROMPT_MAX_LENGTH
    assert resolve_system_prompt(override=prompt) == prompt


def test_resolve_system_prompt_strips_real_control_characters():
    """Validation criterion: sécurité -- le prompt est correctement
    sanitizé (baseline réelle : caractères de contrôle retirés)."""
    assert resolve_system_prompt(override="Be helpful.\x00\x01") == "Be helpful."


def test_resolve_system_prompt_rejects_an_empty_string():
    with pytest.raises(ValueError):
        resolve_system_prompt(override="   ")


# ------------------------------- 4.3.5 max_tokens -------------------------------


def test_resolve_max_tokens_falls_back_to_the_real_default():
    """Validation criterion: le fallback fonctionne."""
    assert resolve_max_tokens() == DEFAULT_SETTINGS["max_tokens"]


def test_resolve_max_tokens_reads_from_real_organization_settings():
    assert resolve_max_tokens({"max_tokens": 8192}) == 8192


def test_resolve_max_tokens_override_wins():
    assert resolve_max_tokens({"max_tokens": 8192}, override=100) == 100


def test_resolve_max_tokens_rejects_zero_and_negative():
    """Validation criterion: robustesse -- valeur invalide."""
    with pytest.raises(ValueError):
        resolve_max_tokens(override=0)
    with pytest.raises(ValueError):
        resolve_max_tokens(override=-1)


def test_resolve_max_tokens_rejects_a_real_too_large_value():
    with pytest.raises(ValueError):
        resolve_max_tokens(override=settings.MAX_TOKENS_CEILING + 1)


def test_resolve_max_tokens_accepts_the_real_ceiling():
    assert resolve_max_tokens(override=settings.MAX_TOKENS_CEILING) == settings.MAX_TOKENS_CEILING


# ------------------------------- resolve_llm_config -------------------------------


def test_resolve_llm_config_combines_every_real_resolver():
    """Validation criterion: cohérence -- une configuration complète et
    cohérente est produite."""
    config = resolve_llm_config({"llm_provider": "openai", "temperature": 0.3})
    assert config["provider"] == "openai"
    assert config["model"] == settings.OPENAI_MODEL
    assert config["temperature"] == 0.3
    assert config["top_p"] == DEFAULT_SETTINGS["top_p"]
    assert config["max_tokens"] == DEFAULT_SETTINGS["max_tokens"]
    assert config["system_prompt"] == DEFAULT_SETTINGS["system_prompt"]


def test_resolve_llm_config_respects_real_overrides():
    config = resolve_llm_config(overrides={"provider": "mistral", "temperature": 1.5, "max_tokens": 500})
    assert config["provider"] == "mistral"
    assert config["model"] == settings.MISTRAL_MODEL
    assert config["temperature"] == 1.5
    assert config["max_tokens"] == 500
