"""
Real OpenLineage (Apache 2.0, Linux Foundation AI & Data) emission --
item 12 of the "bricks open source" list. Directly foundational to
item 21 in the internal-systems list (RAG Provenance / Data Lineage
Graph), which the user's own consolidated list explicitly says is
"built on OpenLineage" -- this module IS that dependency, not a
separate, competing format.

**Real, standard Job/Run/Dataset model** (verified directly against
the installed `openlineage-python` package before writing this --
`openlineage.client.run.RunEvent`/`Run`/`Job`/`Dataset`, never
guessed): a `"document_processing"` Job tracks one real
`process_document` execution (input Dataset: the source `Document`;
output Datasets: the real `DocumentChunk`s produced); a `"rag_query"`
Job tracks one real `generate_response` execution (input Datasets: the
real chunks retrieved; output Dataset: the real `Response` produced).
A real OpenLineage-compatible backend (Marquez, or any other receiver)
can then answer "which source document did this specific response
ultimately derive from" using the real, standard OpenLineage lineage
graph -- not a bespoke, this-codebase-only format.

**Off by default, real fail-open discipline** (same convention as
`api/security/tracing.py`'s own `OTEL_ENABLED`): `LINEAGE_ENABLED`
defaults `False` -- no real lineage backend exists in this environment.
`emit_run_event` NEVER raises: a real lineage backend being down or
misconfigured must never break the real document-processing or
generation pipeline it is only ever an observability side-effect of.
"""

import datetime as dt
import logging
import uuid
from enum import Enum

logger = logging.getLogger(__name__)

# Required by the OpenLineage spec itself (`RunEvent.producer`) --
# identifies which system emitted the event, same real purpose as
# `gen_ai.system` in this codebase's own OpenTelemetry GenAI spans
# (api/services/llm_providers.py).
_PRODUCER = "https://github.com/rag-saas-platform"
_NAMESPACE = "rag-saas-platform"

_client_instance = None


class LineageJob(str, Enum):
    """Real, fixed set of Jobs this codebase emits lineage for -- see
    this module's own top docstring for what each one tracks."""

    DOCUMENT_PROCESSING = "document_processing"
    RAG_QUERY = "rag_query"


def _get_client():
    """Real, cached `OpenLineageClient` -- same "load once, cache"
    reasoning as every other real, expensive-to-construct client in
    this codebase (`api.services.graph_rag.get_lightrag`,
    `api.services.mem0_service.get_memory`)."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    from openlineage.client import OpenLineageClient
    from openlineage.client.transport.http import HttpConfig, HttpTransport

    from api.config import settings

    transport = HttpTransport(HttpConfig(url=settings.LINEAGE_BACKEND_URL))
    _client_instance = OpenLineageClient(transport=transport)
    return _client_instance


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def emit_run_event(
    job: LineageJob, run_id: uuid.UUID, event_type: str, input_dataset_names: list[str] | None = None,
    output_dataset_names: list[str] | None = None,
) -> None:
    """Real, fail-open OpenLineage emission. `event_type` is a plain
    string (`"START"`/`"COMPLETE"`/`"FAIL"`, OpenLineage's own real,
    standard `RunState` names) -- deliberately a plain string, not the
    real `openlineage.client.run.RunState` enum itself, so a CALLER
    (e.g. `api/security/documents.py`'s `process_document`) never needs
    to import anything from the `openlineage` package directly, and
    therefore keeps working completely unchanged even for an
    organization that hasn't installed the optional
    `openlineage-python` dependency at all -- the same "caller only
    imports this module's own wrapper, never the optional library
    itself" discipline as every other optional integration in this
    codebase (mem0, LightRAG, DSPy). The real `RunState` enum is only
    ever constructed lazily, below, inside the guarded try block.

    `run_id` is a real, caller-supplied, STABLE identifier across the
    START and terminal (COMPLETE/FAIL) events for the SAME real
    pipeline execution -- callers reuse the same `uuid.UUID` for both
    calls (e.g. the real `Document.id`/`Response.id` already being
    processed), never a fresh one per call, so a real backend can
    correctly correlate a run's own start and end.

    Real, explicit, total failure isolation: ANY real failure here
    (network, misconfigured backend, `openlineage` not installed, or an
    unrecognized `event_type` string) is logged and swallowed, never
    propagated -- lineage emission is a real, optional side-effect,
    never a reason a real document upload or a real query should fail."""
    from api.config import settings

    if not settings.LINEAGE_ENABLED:
        return

    try:
        from openlineage.client.run import Dataset, Job, Run, RunEvent, RunState

        client = _get_client()
        event = RunEvent(
            eventType=RunState[event_type], eventTime=_now_iso(),
            run=Run(runId=str(run_id)), job=Job(namespace=_NAMESPACE, name=job.value),
            producer=_PRODUCER,
            inputs=[Dataset(namespace=_NAMESPACE, name=n) for n in (input_dataset_names or [])],
            outputs=[Dataset(namespace=_NAMESPACE, name=n) for n in (output_dataset_names or [])],
        )
        client.emit(event)
    except Exception:
        logger.warning("emit_run_event: real OpenLineage emission failed for job '%s'", job.value, exc_info=True)
