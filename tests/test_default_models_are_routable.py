"""Every Anthropic model this product proposes or defaults to must be routable by the LiteLLM version that is installed.

A real end-to-end run found that the default `claude-3-5-sonnet-20241022` (retired) was no longer known to LiteLLM, so EVERY default chat
answer failed with "LLM Provider NOT provided". The mocks used elsewhere in the suite never saw it."""

import contextlib
import io

import litellm
import pytest

from api.config import settings
from api.services.agent_models import MODEL_CATALOG
from api.services.llm_config import _COST_AWARE_CANDIDATES


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
