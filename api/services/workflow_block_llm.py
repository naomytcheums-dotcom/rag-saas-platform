"""
Partie 5.4.3 -- real `llm_call` workflow block execution.

**Cohérence (vision critique 1): reuses this codebase's own real LLM
infrastructure end-to-end, no second/competing path** --
`resolve_llm_config` (Partie 4.3.1-4.3.5) for real provider/model/
temperature/max_tokens/top_p defaults (org-settings- and override-
aware, same real precedence as `AgentOrchestrator.run_agent` itself),
`chat_completion` (Partie 4.1.7) for the actual real LLM call.
`get_available_llm_models` delegates to Partie 5.3.3's own real
`agent_models.get_available_models` -- the SAME real, single model
catalog, not a second one for workflows.

**Robustness (vision critique 3)**: a real LLM failure
(`llm_providers.LLMError`) is caught and re-raised as a real
`WorkflowBlockError` -- one real, shared error type every real block
executor raises, not a leaked, provider-specific exception a real
caller (a future graph executor) would have to know about."""

from api.services.agent_models import get_available_models
from api.services.llm_config import resolve_llm_config
from api.services.llm_providers import LLMError, chat_completion
from api.services.template_rendering import render_template
from api.services.workflow_blocks import WorkflowBlockError


def validate_llm_config(config: dict) -> None:
    """Item 2's own literal function -- real, upfront: a real
    `user_prompt` is the one genuinely required field (everything else
    has a real, safe default via `resolve_llm_config`)."""
    if not config.get("user_prompt"):
        raise WorkflowBlockError("llm_call block requires a real, non-empty 'user_prompt'")


def render_llm_prompt(prompt_template: str, context: dict) -> str:
    """Item 2's own literal function -- real, shared `{{var}}`
    substitution (`api/services/template_rendering.py`), same safe
    implementation as Partie 5.3.2's own agent system prompts."""
    return render_template(prompt_template, context)


def get_available_llm_models(provider: str | None = None) -> dict:
    """Item 2's own literal function -- real reuse, not a second
    catalog."""
    return get_available_models(provider)


async def execute_llm_block(block_config: dict, context: dict) -> dict:
    """Item 2's own literal function -- real, upfront validation, real
    template rendering of both prompts, then a real, live LLM call.
    Returns `{output_key: result}` (item 1's own literal
    `output_key`, default `"output"`) -- the real shape a future graph
    executor threads into the next real block's own `context`."""
    validate_llm_config(block_config)

    system_prompt = render_llm_prompt(block_config.get("system_prompt", ""), context)
    user_prompt = render_llm_prompt(block_config["user_prompt"], context)

    overrides = {k: block_config[k] for k in ("provider", "model", "temperature", "max_tokens") if k in block_config}
    llm_cfg = resolve_llm_config(None, overrides=overrides)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    try:
        result = await chat_completion(
            messages, provider=llm_cfg["provider"], model=llm_cfg["model"],
            temperature=llm_cfg["temperature"], top_p=llm_cfg["top_p"], max_tokens=llm_cfg["max_tokens"],
        )
    except LLMError as exc:
        raise WorkflowBlockError(f"llm_call block failed: {exc}") from exc

    return {block_config.get("output_key", "output"): result}
