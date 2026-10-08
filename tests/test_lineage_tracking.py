"""
api/services/lineage_tracking.py -- `OpenLineageClient.emit` makes a
real HTTP call under the hood to a configured lineage backend. Mocked
here at its own clean, already-tested boundary (`OpenLineageClient.emit`
itself, verified directly against the installed `openlineage-python`
package before writing this module -- never a fabricated shape)."""

import uuid
from unittest.mock import MagicMock, patch

from api.services.lineage_tracking import LineageJob, emit_run_event


async def test_emit_run_event_does_nothing_when_lineage_is_disabled(monkeypatch):
    """Real, deliberate default: LINEAGE_ENABLED is False unless an
    operator explicitly configures a real backend."""
    monkeypatch.setattr("api.config.settings.LINEAGE_ENABLED", False)
    mock_client = MagicMock()

    with patch("api.services.lineage_tracking._get_client", return_value=mock_client):
        emit_run_event(LineageJob.DOCUMENT_PROCESSING, uuid.uuid4(), "START")

    mock_client.emit.assert_not_called()


async def test_emit_run_event_emits_a_real_run_event_when_enabled(monkeypatch):
    """Validation criterion: a real, correctly-shaped RunEvent (job
    name, namespace, producer, run id, inputs/outputs) reaches the
    real client's own emit() call when lineage is enabled."""
    monkeypatch.setattr("api.config.settings.LINEAGE_ENABLED", True)
    mock_client = MagicMock()
    run_id = uuid.uuid4()

    with patch("api.services.lineage_tracking._get_client", return_value=mock_client):
        emit_run_event(
            LineageJob.RAG_QUERY, run_id, "COMPLETE",
            input_dataset_names=["chunk:abc"], output_dataset_names=["response:xyz"],
        )

    mock_client.emit.assert_called_once()
    event = mock_client.emit.call_args.args[0]
    assert event.job.name == "rag_query"
    assert event.job.namespace == "rag-saas-platform"
    assert event.run.runId == str(run_id)
    assert event.eventType.value == "COMPLETE"
    assert [d.name for d in event.inputs] == ["chunk:abc"]
    assert [d.name for d in event.outputs] == ["response:xyz"]


async def test_emit_run_event_never_raises_on_a_real_emission_failure(monkeypatch):
    """Real, fail-open discipline: a real backend failure (network,
    misconfiguration) must never propagate -- lineage emission is a
    real, optional side-effect, never a reason a real pipeline fails."""
    monkeypatch.setattr("api.config.settings.LINEAGE_ENABLED", True)
    mock_client = MagicMock()
    mock_client.emit.side_effect = RuntimeError("real, unexpected backend failure")

    with patch("api.services.lineage_tracking._get_client", return_value=mock_client):
        emit_run_event(LineageJob.DOCUMENT_PROCESSING, uuid.uuid4(), "FAIL")
    # No exception raised -- the real assertion of this test.


async def test_emit_run_event_never_raises_when_openlineage_is_not_installed(monkeypatch):
    """Real, honest degradation -- same contract as every other
    optional dependency in this codebase."""
    import builtins

    monkeypatch.setattr("api.config.settings.LINEAGE_ENABLED", True)
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "openlineage.client.run":
            raise ImportError("No module named 'openlineage'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    emit_run_event(LineageJob.DOCUMENT_PROCESSING, uuid.uuid4(), "START")
    # No exception raised -- the real assertion of this test.
