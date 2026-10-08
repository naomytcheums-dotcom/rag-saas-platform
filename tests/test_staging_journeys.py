"""Offline safety checks for the live journey runner; no staging connections."""

import io
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from botocore.exceptions import ClientError

from scripts import staging_journeys as journeys
from scripts.staging_target import StagingTargetError


@pytest.fixture
def prerequisites(monkeypatch):
    for name in (
        *journeys.S3_VARIABLES,
        *journeys.PROVIDER_KEYS.values(),
        "STAGING_JOURNEY_MODEL",
        "LLM_DEFAULT_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(journeys, "dotenv_values", lambda _path: {})
    monkeypatch.setattr(journeys, "staging_url", lambda: "synthetic-target")
    monkeypatch.setattr(
        journeys, "isolated_environment", lambda _url: {"RAG_ENV_FILE": "synthetic"}
    )
    for name in journeys.S3_VARIABLES:
        monkeypatch.setenv(name, "synthetic-test-value")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-test-value")


@pytest.mark.parametrize("name", journeys.S3_VARIABLES)
def test_each_missing_storage_setting_blocks_the_runner(
    prerequisites, monkeypatch, name
):
    monkeypatch.delenv(name)
    _env, missing = journeys.prerequisites()
    assert name in missing
    assert all("synthetic-test-value" not in item for item in missing)


def test_missing_provider_key_is_named_without_its_value(prerequisites, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    _env, missing = journeys.prerequisites()
    assert missing == ["ANTHROPIC_API_KEY"]


def test_provider_selection_checks_the_matching_key(prerequisites, monkeypatch):
    monkeypatch.setenv("STAGING_JOURNEY_MODEL", "openai/gpt-4o-mini")
    env, missing = journeys.prerequisites()
    assert missing == ["OPENAI_API_KEY"]
    assert env["STAGING_JOURNEY_PROVIDER"] == "openai"
    assert env["LLM_DEFAULT_MODEL"] == "gpt-4o-mini"


def test_target_refusal_prevents_any_execution(prerequisites, monkeypatch, capsys):
    def refuse():
        raise StagingTargetError(
            "Missing staging allowlist variable: STAGING_ALLOWED_DIRECT_HOST; target refused."
        )

    monkeypatch.setattr(journeys, "staging_url", refuse)
    monkeypatch.setattr("sys.argv", ["staging_journeys.py", "--execute"])
    assert journeys.main() == 2
    output = capsys.readouterr().out
    assert "STAGING_ALLOWED_DIRECT_HOST" in output
    assert output.count("HTTP=[] rows=NOT_MEASURED") == len(journeys.JOURNEYS)
    assert "synthetic-test-value" not in output


def test_dry_run_never_starts_live_execution(prerequisites, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["staging_journeys.py"])
    assert journeys.main() == 0
    assert "no connection or process started" in capsys.readouterr().out


def test_fixture_files_are_real_and_contain_the_run_marker():
    import pymupdf
    from docx import Document

    files = journeys.fixture_files("synthetic-marker")
    assert b"synthetic-marker" in files["txt"][0]
    with pymupdf.open(stream=files["pdf"][0], filetype="pdf") as pdf:
        assert "synthetic-marker" in pdf[0].get_text()
    docx = Document(io.BytesIO(files["docx"][0]))
    assert "synthetic-marker" in docx.paragraphs[0].text


async def test_http_failure_never_displays_the_response_payload(capsys):
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(502, text="sensitive-provider-payload")
    )
    async with httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1"
    ) as client:
        runner = journeys.Journeys(client, None, 1)

        async def request():
            return await runner.request("POST", "/synthetic")

        await runner.step("synthetic", request)
        assert runner.failures == 1
    output = capsys.readouterr().out
    assert "FAIL HTTP=[502]" in output
    assert "sensitive-provider-payload" not in output


async def test_poll_rejects_failed_jobs_without_exposing_job_errors():
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={"status": "failed", "error": "sensitive-job-payload"},
        )
    )
    async with httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1"
    ) as client:
        runner = journeys.Journeys(client, None, 1)
        with pytest.raises(journeys.JourneyFailure, match="status=failed") as error:
            await runner.poll("/synthetic")
    assert "sensitive-job-payload" not in str(error.value)


async def test_poll_surfaces_a_worker_crash_before_requesting_job_status():
    child = MagicMock()
    child.check.side_effect = journeys.JourneyFailure("local service exited: code=1")
    async with httpx.AsyncClient(base_url="http://127.0.0.1") as client:
        runner = journeys.Journeys(client, None, 1, children=[child])
        with pytest.raises(journeys.JourneyFailure, match="code=1"):
            await runner.poll("/synthetic")
    child.check.assert_called_once()


@pytest.fixture
def cleanup_resources(monkeypatch):
    import boto3

    for name in journeys.S3_VARIABLES:
        monkeypatch.setenv(name, "synthetic-test-value")
    session = AsyncMock()
    session.scalar.side_effect = [SimpleNamespace(id=uuid.uuid4()), 0, 0, 0, 0]
    session.scalars.side_effect = [
        SimpleNamespace(all=lambda: [uuid.uuid4()]) for _ in range(3)
    ]
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=False)
    s3 = MagicMock()
    s3.get_paginator.return_value.paginate.return_value = [{"Contents": []}]
    s3.list_objects_v2.return_value = {"KeyCount": 0}
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: s3)
    return lambda: context, session, s3


async def test_cleanup_checks_cascades_and_reports_zero_remaining_rows(
    cleanup_resources, capsys
):
    factory, session, s3 = cleanup_resources
    async with httpx.AsyncClient() as client:
        runner = journeys.Journeys(client, factory, 1)
        await runner.cleanup()
    assert session.execute.await_count == 2
    assert session.scalar.await_count == 5
    session.commit.assert_awaited_once()
    s3.close.assert_called_once()
    assert "users=0 organizations=0 chunks=0 citations=0" in capsys.readouterr().out


async def test_storage_cleanup_failure_retains_references_and_emits_recovery_hint(
    cleanup_resources, capsys
):
    factory, session, s3 = cleanup_resources
    s3.list_objects_v2.side_effect = ClientError(
        {"Error": {"Code": "503", "Message": "sensitive-storage-payload"}},
        "ListObjectsV2",
    )
    async with httpx.AsyncClient() as client:
        runner = journeys.Journeys(client, factory, 1)
        with pytest.raises(ClientError):
            await runner.cleanup()
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()
    s3.close.assert_called_once()
    output = capsys.readouterr().out
    assert "cleanup: FAIL type=ClientError" in output
    assert "--cleanup-run <marker> --execute" in output
    assert "sensitive-storage-payload" not in output
