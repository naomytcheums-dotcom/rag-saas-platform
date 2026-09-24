# Workflow Engine (developer reference)

`api/services/workflow_engine.py` is a real graph executor: a
`Workflow`'s `nodes`/`edges` (JSON, edited via the frontend workflow
builder or `POST /organizations/{org_id}/workflows`) are walked node by
node, threading an accumulated `context` dict between them.

## Node types

| `type` | What it does |
|---|---|
| `trigger` | Entry point, no-op — every graph needs exactly one. |
| `llm_call` | A real LLM completion (`api/services/workflow_block_llm.py`). |
| `rag_search` | Retrieval against the org's knowledge base. |
| `web_search` | A real web search call. |
| `http_call` | An outbound HTTP request, SSRF-protected (`ssrf_safe_client`). |
| `condition` | Branches to a different next node based on `context`. |
| `code` | Runs a real, sandboxed snippet (`api/services/workflow_block_code.py`). |
| `email` | Sends a real email. |
| `calendar` | Creates/reads a real calendar event. |
| `database` | A real, read-only, allow-listed SQL query against the org's own tables. |
| `human` | Pauses the run for a human decision (see below). |

## Variable interpolation

A node's own config strings can reference `context` values with
`{{key}}` (e.g. a prompt `"Answer: {{question}}"`) — substituted before
that node runs. Every prior node's own real output is merged into
`context` by its `output_key`.

## Human-in-the-loop

A `human` block (`api/services/workflow_block_human.py`) pauses the run
(`WorkflowRunStatus.waiting_human`) and creates a `WorkflowHumanInput`
row. The run resumes (`resume_workflow_run`) only once that row is
submitted (`POST /workflows/runs/{run_id}/human-blocks/{block_id}/submit`)
— `confirm` (yes/no) and free-text `input_type`s are supported today; a
richer, multi-choice options list exists at the model level
(`WorkflowHumanInput.options`, `choice` type) but has no dedicated
frontend editor yet — see ROADMAP.md.

The workflow's own creator gets a real, persisted, in-app notification
the moment a run pauses on a `human` block.

## Execution history

Every real node execution (success, failure, or a `human`-block pause)
is recorded in `WorkflowNodeExecution` — `step_number`, `node_id`,
`node_type`, `input`, `output`, `duration_ms`, `status`, `error`.
`GET /workflows/runs/{run_id}/trace` returns the full, ordered history
for one run; `GET /workflows/runs/{run_id}/stream` gives the same
events live over SSE while a run is in progress.

## Safety limits

`MAX_STEPS` caps total node executions per run — a cyclic graph fails
with an honest error instead of looping forever.
