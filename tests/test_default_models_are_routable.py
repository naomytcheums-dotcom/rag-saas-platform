"""Every model this product proposes or defaults to, for every provider, must be routable by the installed LiteLLM as actually sent.

A real end-to-end run found that the default `claude-3-5-sonnet-20241022` (retired) was no longer known to LiteLLM, so EVERY default chat
answer failed with "LLM Provider NOT provided". The mocks used elsewhere in the suite never saw it."""

import contextlib
import io

import litellm
import pytest

from api.config import settings
from api.services.agent_models import MODEL_CATALOG
from api.services.llm_config import _COST_AWARE_CANDIDATES
from api.services.llm_providers import PROVIDER_SETTINGS, _provider_kwargs, to_litellm_model


def _routable(model: str) -> bool:
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            litellm.get_llm_provider(model)
            return True
        except Exception:  # noqa: BLE001 -- any failure means the model cannot be routed
            return False


ANTHROPIC_IDS = sorted({settings.LLM_DEFAULT_MODEL, settings.ANTHROPIC_MODEL, *MODEL_CATALOG["anthropic"], *_COST_AWARE_CANDIDATES["anthropic"]})


@pytest.mark.parametrize("model", ANTHROPIC_IDS)
def test_every_default_anthropic_model_is_routable(model):
    assert _routable(model), f"{model!r} is not routable by the installed LiteLLM (retired or misspelled): the default chat would fail"


CATALOG_PAIRS = sorted((provider, model) for provider, models in MODEL_CATALOG.items() for model in models)
CONFIG_DEFAULTS = sorted(
    (provider, getattr(settings, PROVIDER_SETTINGS[provider]["model"])) for provider in MODEL_CATALOG
)
COST_AWARE_PAIRS = sorted((provider, model) for provider, models in _COST_AWARE_CANDIDATES.items() for model in models)
ALL_PAIRS = sorted(set(CATALOG_PAIRS) | set(CONFIG_DEFAULTS) | set(COST_AWARE_PAIRS))


@pytest.mark.parametrize(("provider", "model"), ALL_PAIRS)
def test_every_proposed_model_of_every_provider_is_routable_as_sent(provider, model):
    """A bare catalog name (`gemini-2.5-pro`, `mistral-small-latest`, `llama3.1`) must reach LiteLLM with its provider prefix."""
    sent = to_litellm_model(provider, model)
    assert _routable(sent), f"{provider}/{model!r} is sent as {sent!r}, which the installed LiteLLM cannot route"


@pytest.mark.parametrize(("provider", "model"), [p for p in ALL_PAIRS if p[0] != "ollama"])
def test_every_proposed_hosted_model_is_known_to_the_litellm_price_map(provider, model):
    """Absent from `litellm.model_cost` usually means retired (the Gemini 1.5 models were): no cost, often no route."""
    assert to_litellm_model(provider, model) in litellm.model_cost


@pytest.mark.parametrize(("provider", "model"), CATALOG_PAIRS)
def test_provider_kwargs_sends_the_prefixed_model(provider, model, monkeypatch):
    key_setting = PROVIDER_SETTINGS[provider]["api_key"]
    if key_setting:
        monkeypatch.setattr(settings, key_setting, "test-key-not-real")
    kwargs = _provider_kwargs(provider, model)
    assert kwargs["model"] == to_litellm_model(provider, model)
    assert _routable(kwargs["model"])


def test_already_prefixed_names_are_not_double_prefixed():
    assert to_litellm_model("gemini", "gemini/gemini-2.5-pro") == "gemini/gemini-2.5-pro"
    assert to_litellm_model("anthropic", "claude-sonnet-5-5") == "claude-sonnet-5-5"


@pytest.mark.parametrize(
    ("pricing_key", "litellm_id"),
    [
        ("claude-sonnet-5-5", "claude-sonnet-5-5"),
        ("claude-haiku-4-5", "claude-haiku-4-5"),
        ("gpt-4o", "gpt-4o"),
        ("gpt-4o-mini", "gpt-4o-mini"),
        ("gemini-2.5-pro", "gemini/gemini-2.5-pro"),
        ("gemini-2.5-flash", "gemini/gemini-2.5-flash"),
        ("mistral-large", "mistral/mistral-large-latest"),
        ("mistral-small", "mistral/mistral-small-latest"),
    ],
)
def test_cost_pricing_matches_the_litellm_price_map(pricing_key, litellm_id):
    entry = litellm.model_cost[litellm_id]
    assert settings.COST_MODEL_PRICING[pricing_key]["input"] == pytest.approx(entry["input_cost_per_token"] * 1_000_000)
    assert settings.COST_MODEL_PRICING[pricing_key]["output"] == pytest.approx(entry["output_cost_per_token"] * 1_000_000)
