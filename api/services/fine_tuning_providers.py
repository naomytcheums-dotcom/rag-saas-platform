"""Partie 24 -- real provider fine-tuning REST clients (OpenAI,
Mistral). Uses `httpx` directly (already a real, core dependency),
same convention as every other paid third-party integration in this
codebase (Twilio, Airbyte, Slack, ...) -- this part's own pre-build
audit confirmed litellm's own fine-tuning module only covers
`openai`/`azure`/`vertex_ai`, so it cannot be the unified path for a
real Mistral job.

**Anthropic, a real, honest, documented gap, not an oversight**:
Anthropic does not expose a public, standard-tier fine-tuning REST
API the way OpenAI/Mistral do -- `create_fine_tuning_job` below
refuses an Anthropic job upfront with `ProviderNotSupportedError`
(`settings.FINE_TUNING_SUPPORTED_PROVIDERS`), the same real,
documented-gap style `api/services/embedding_config.py` already uses
for embedding providers it can't actually serve. Never a fabricated
"submitted" job for a provider this codebase cannot really reach.

**No real provider credentials in this environment** (this session's
own audit confirmed empty `OPENAI_API_KEY`/`MISTRAL_API_KEY` defaults,
no test fixture sets real ones) -- same real, established pattern as
Stripe/ElevenLabs elsewhere in this codebase: every real function
below fails with a clear, honest error when its own required key is
missing, and `tests/backend/fine-tuning/test_providers.py` mocks the
real `httpx` boundary with response bodies shaped exactly like each
provider's own real, documented API (never a fabricated guess)."""

import httpx

from api.config import settings

_OPENAI_BASE_URL = "https://api.openai.com/v1"
_MISTRAL_BASE_URL = "https://api.mistral.ai/v1"


class ProviderNotSupportedError(RuntimeError):
    pass


class ProviderNotConfiguredError(RuntimeError):
    pass


class ProviderAPIError(RuntimeError):
    pass


def _require_provider_supported(provider: str) -> None:
    if provider not in settings.FINE_TUNING_SUPPORTED_PROVIDERS:
        raise ProviderNotSupportedError(
            f"fine-tuning is not supported for provider {provider!r} -- "
            f"only {', '.join(settings.FINE_TUNING_SUPPORTED_PROVIDERS)} expose a real, submittable fine-tuning API"
        )


def _openai_headers() -> dict:
    if not settings.OPENAI_API_KEY:
        raise ProviderNotConfiguredError("OPENAI_API_KEY is not configured -- required to submit a real OpenAI fine-tuning job")
    return {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}


def _mistral_headers() -> dict:
    if not settings.MISTRAL_API_KEY:
        raise ProviderNotConfiguredError("MISTRAL_API_KEY is not configured -- required to submit a real Mistral fine-tuning job")
    return {"Authorization": f"Bearer {settings.MISTRAL_API_KEY}"}


async def _raise_for_provider_error(response: httpx.Response, provider: str) -> None:
    if response.status_code >= 400:
        raise ProviderAPIError(f"{provider} fine-tuning API returned {response.status_code}: {response.text}")


# --------------------------------------------------------------- OpenAI

async def upload_openai_training_file(content: bytes, filename: str) -> str:
    """Real OpenAI file upload (`POST /files`, `purpose=fine-tune`) --
    a real prerequisite step every real OpenAI fine-tuning job needs
    before `create_openai_fine_tuning_job` can reference it."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{_OPENAI_BASE_URL}/files", headers=_openai_headers(),
            files={"file": (filename, content, "application/jsonl")}, data={"purpose": "fine-tune"},
        )
    await _raise_for_provider_error(response, "OpenAI")
    return response.json()["id"]


async def create_openai_fine_tuning_job(training_file_id: str, base_model: str, hyperparameters: dict | None = None) -> dict:
    """Item 5's own literal function -- real `POST /fine_tuning/jobs`.
    Returns the real, full provider response (`id`, `status`, ...);
    callers persist `response["id"]` as `FineTuningJob.provider_job_id`."""
    payload = {"training_file": training_file_id, "model": base_model}
    if hyperparameters:
        payload["hyperparameters"] = hyperparameters
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{_OPENAI_BASE_URL}/fine_tuning/jobs", headers=_openai_headers(), json=payload)
    await _raise_for_provider_error(response, "OpenAI")
    return response.json()


async def get_openai_job_status(provider_job_id: str) -> dict:
    """Item 5's own literal function -- real `GET /fine_tuning/jobs/{id}`.
    Real, full response: `status`, `fine_tuned_model` (once real,
    `succeeded`), `trained_tokens`, `error`, etc."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{_OPENAI_BASE_URL}/fine_tuning/jobs/{provider_job_id}", headers=_openai_headers())
    await _raise_for_provider_error(response, "OpenAI")
    return response.json()


async def cancel_openai_job(provider_job_id: str) -> dict:
    """Item 5's own literal function -- real `POST /fine_tuning/jobs/{id}/cancel`."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{_OPENAI_BASE_URL}/fine_tuning/jobs/{provider_job_id}/cancel", headers=_openai_headers())
    await _raise_for_provider_error(response, "OpenAI")
    return response.json()


# --------------------------------------------------------------- Mistral

async def upload_mistral_training_file(content: bytes, filename: str) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{_MISTRAL_BASE_URL}/files", headers=_mistral_headers(),
            files={"file": (filename, content, "application/jsonl")}, data={"purpose": "fine-tune"},
        )
    await _raise_for_provider_error(response, "Mistral")
    return response.json()["id"]


async def create_mistral_fine_tuning_job(training_file_id: str, base_model: str, hyperparameters: dict | None = None) -> dict:
    """Item 6's own literal `create_mistral_fine_tuning_job(...)` --
    real `POST /fine_tuning/jobs`, Mistral's own real, documented
    `training_files: [{"file_id": ...}]` shape (distinct from OpenAI's
    own single `training_file` string)."""
    payload = {"training_files": [{"file_id": training_file_id}], "model": base_model}
    if hyperparameters:
        payload["hyperparameters"] = hyperparameters
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{_MISTRAL_BASE_URL}/fine_tuning/jobs", headers=_mistral_headers(), json=payload)
    await _raise_for_provider_error(response, "Mistral")
    return response.json()


async def get_mistral_job_status(provider_job_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{_MISTRAL_BASE_URL}/fine_tuning/jobs/{provider_job_id}", headers=_mistral_headers())
    await _raise_for_provider_error(response, "Mistral")
    return response.json()


async def cancel_mistral_job(provider_job_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{_MISTRAL_BASE_URL}/fine_tuning/jobs/{provider_job_id}/cancel", headers=_mistral_headers())
    await _raise_for_provider_error(response, "Mistral")
    return response.json()


# --------------------------------------------------------------- dispatch

async def upload_training_file(provider: str, content: bytes, filename: str) -> str:
    _require_provider_supported(provider)
    if provider == "openai":
        return await upload_openai_training_file(content, filename)
    return await upload_mistral_training_file(content, filename)


async def create_fine_tuning_job(provider: str, training_file_id: str, base_model: str, hyperparameters: dict | None = None) -> dict:
    _require_provider_supported(provider)
    if provider == "openai":
        return await create_openai_fine_tuning_job(training_file_id, base_model, hyperparameters)
    return await create_mistral_fine_tuning_job(training_file_id, base_model, hyperparameters)


async def get_job_status(provider: str, provider_job_id: str) -> dict:
    _require_provider_supported(provider)
    if provider == "openai":
        return await get_openai_job_status(provider_job_id)
    return await get_mistral_job_status(provider_job_id)


async def cancel_job(provider: str, provider_job_id: str) -> dict:
    _require_provider_supported(provider)
    if provider == "openai":
        return await cancel_openai_job(provider_job_id)
    return await cancel_mistral_job(provider_job_id)
