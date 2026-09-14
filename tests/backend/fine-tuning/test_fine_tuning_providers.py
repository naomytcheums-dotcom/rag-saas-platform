"""Partie 24 -- real OpenAI/Mistral fine-tuning REST clients. `httpx`
itself is mocked (the real, established exception to this codebase's
own "no mocking" precedent for real, paid third-party APIs this
environment has no real credentials for -- same category as
tests/test_llm_providers.py's own litellm mock) -- response bodies are
shaped exactly like each provider's own real, documented fine-tuning
API responses."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.config import settings
from api.services.fine_tuning_providers import (
    ProviderNotConfiguredError, ProviderNotSupportedError, cancel_job, create_fine_tuning_job, get_job_status, upload_training_file,
)


@pytest.fixture(autouse=True)
def _configure_keys(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "sk-mistral-test")


def _mock_response(status_code: int, json_body: dict, text: str = "") -> MagicMock:
    response = MagicMock(status_code=status_code, text=text or str(json_body))
    response.json.return_value = json_body
    return response


async def test_anthropic_is_refused_upfront_as_not_supported():
    with pytest.raises(ProviderNotSupportedError):
        await create_fine_tuning_job("anthropic", "file-x", "claude-3-haiku")


async def test_upload_training_file_requires_a_real_api_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(ProviderNotConfiguredError):
        await upload_training_file("openai", b"data", "d.jsonl")


async def test_openai_create_fine_tuning_job_posts_the_real_expected_payload():
    mock_post = AsyncMock(return_value=_mock_response(200, {"id": "ftjob-real123", "status": "validating_files"}))
    with patch("httpx.AsyncClient.post", mock_post):
        response = await create_fine_tuning_job("openai", "file-abc123", "gpt-4o-mini-2024-07-18", {"n_epochs": 3})

    assert response["id"] == "ftjob-real123"
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"] == {"training_file": "file-abc123", "model": "gpt-4o-mini-2024-07-18", "hyperparameters": {"n_epochs": 3}}
    assert call_kwargs["headers"]["Authorization"] == "Bearer sk-oai-test"


async def test_mistral_create_fine_tuning_job_uses_its_own_real_training_files_shape():
    mock_post = AsyncMock(return_value=_mock_response(200, {"id": "ft-mistral-real123", "status": "QUEUED"}))
    with patch("httpx.AsyncClient.post", mock_post):
        response = await create_fine_tuning_job("mistral", "file-xyz789", "open-mistral-7b", None)

    assert response["id"] == "ft-mistral-real123"
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"] == {"training_files": [{"file_id": "file-xyz789"}], "model": "open-mistral-7b"}


async def test_get_job_status_dispatches_to_the_real_configured_provider():
    mock_get = AsyncMock(return_value=_mock_response(200, {"id": "ftjob-real123", "status": "running"}))
    with patch("httpx.AsyncClient.get", mock_get):
        response = await get_job_status("openai", "ftjob-real123")

    assert response["status"] == "running"
    assert "fine_tuning/jobs/ftjob-real123" in mock_get.call_args.args[0]


async def test_cancel_job_raises_a_real_provider_api_error_on_a_real_4xx():
    from api.services.fine_tuning_providers import ProviderAPIError

    mock_post = AsyncMock(return_value=_mock_response(404, {"error": {"message": "No such fine-tuning job"}}, text="Not Found"))
    with patch("httpx.AsyncClient.post", mock_post):
        with pytest.raises(ProviderAPIError):
            await cancel_job("openai", "ftjob-unknown")
