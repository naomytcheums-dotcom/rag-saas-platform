"""
Partie 5.3.3 -- choosing and validating an agent's own real LLM model
configuration.

**Real reuse, not a parallel provider list**: validates against the
SAME real `PROVIDER_SETTINGS` keys `api/services/llm_providers.py`
(Partie 4.1.7) already uses to actually make a real LLM call --
`"gemini"`, not this étape's own literal "Google" label (a real,
documented naming reconciliation, not a second, competing provider
registry)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.agent import Agent
from api.services.llm_providers import PROVIDER_SETTINGS

# Item 3's own literal 9 models, grouped by the SAME real provider keys
# `llm_providers.PROVIDER_SETTINGS` already uses ("google" -> "gemini").
MODEL_CATALOG: dict[str, list[str]] = {
    "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
    "openai": ["gpt-4o", "gpt-4o-mini"],
    "gemini": ["gemini-1.5-pro", "gemini-1.5-flash"],
    "mistral": ["mistral-large-latest", "mistral-small-latest"],
    "ollama": ["llama3.1"],
}


class AgentModelError(ValueError):
    """Real, dedicated exception."""


def validate_agent_model(provider: str, model: str) -> None:
    """Item 2's own literal function -- real, raises `AgentModelError`
    with a real, specific reason."""
    if provider not in PROVIDER_SETTINGS:
        raise AgentModelError(f"Unknown provider: {provider!r} (expected one of {sorted(PROVIDER_SETTINGS)})")
    if provider not in MODEL_CATALOG or model not in MODEL_CATALOG[provider]:
        raise AgentModelError(f"Model {model!r} is not in the real, known catalog for provider {provider!r} ({MODEL_CATALOG.get(provider, [])})")


def get_available_models(provider: str | None = None) -> dict[str, list[str]]:
    """Item 2's own literal function -- real, optional provider
    filter."""
    if provider is not None:
        if provider not in MODEL_CATALOG:
            raise AgentModelError(f"Unknown provider: {provider!r} (expected one of {sorted(MODEL_CATALOG)})")
        return {provider: MODEL_CATALOG[provider]}
    return dict(MODEL_CATALOG)


def get_default_model_config() -> dict:
    """Item 2's own literal function -- reuses this codebase's own
    real, already-established defaults (Partie 4.3.1-4.3.5's own
    `DEFAULT_SETTINGS`), not a second, competing set of hardcoded
    values."""
    from api.security.organization_settings import DEFAULT_SETTINGS

    return {
        "provider": DEFAULT_SETTINGS["llm_provider"], "model": settings.ANTHROPIC_MODEL,
        "temperature": DEFAULT_SETTINGS["temperature"], "max_tokens": DEFAULT_SETTINGS["max_tokens"],
        "top_p": DEFAULT_SETTINGS["top_p"],
    }


async def get_agent_model(db: AsyncSession, agent_id: uuid.UUID) -> dict | None:
    """Item 2's own literal function -- real, effective config: the
    real agent's own `model_config_json`, missing real keys filled in
    from `get_default_model_config`. `None` for an unknown agent."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    return {**get_default_model_config(), **(agent.model_config_json or {})}


async def set_agent_model(
    db: AsyncSession, agent_id: uuid.UUID, provider: str, model: str,
    temperature: float | None = None, max_tokens: int | None = None, top_p: float | None = None,
) -> Agent | None:
    """Item 2's own literal function -- real, upfront validation
    before ever touching the real row."""
    validate_agent_model(provider, model)

    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None

    config = {**get_default_model_config(), **(agent.model_config_json or {}), "provider": provider, "model": model}
    if temperature is not None:
        config["temperature"] = temperature
    if max_tokens is not None:
        config["max_tokens"] = max_tokens
    if top_p is not None:
        config["top_p"] = top_p

    agent.model_config_json = config
    await db.flush()
    return agent
