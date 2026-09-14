# Glossary

Platform-specific terms, as used throughout this codebase and its docs.

**Agent** — a configured chatbot persona: a system prompt, a tool
allowlist, and model config, invoked per conversation turn. See
`api/routers/agents.py`. Distinct from an **autonomous agent** (below).

**Autonomous agent** — an entity that plans and executes a multi-step
goal on its own, via a real tool-calling loop, rather than responding to
a single chat turn. See `AutonomousAgent` in
`api/models/autonomous_agent.py` and
[`docs/autonomous/OVERVIEW.md`](docs/autonomous/OVERVIEW.md).

**Agent plan** — the ordered set of steps an autonomous agent commits to
before executing a goal (`AgentPlan`). Steps are `AgentStep` rows,
executed one at a time.

**Agent memory** — persistent key/value or freeform context an
autonomous agent can write to and read from across steps and, depending
on scope, across runs (`AgentMemory`).

**Agent collaboration** — a bounded, single-call handoff from one
autonomous agent to another (`AgentCollaboration`). Deliberately not a
full nested autonomous run — see
[`docs/autonomous/COLLABORATION.md`](docs/autonomous/COLLABORATION.md).

**Organization (org)** — the top-level multi-tenancy boundary. Nearly
every tenant-scoped table carries an `org_id`, most enforce row-level
security (RLS) on it.

**Workspace** — a grouping inside an organization, used to scope
documents/conversations more narrowly than the whole org.

**Team** — a group of organization members, used for permissions and
notification routing, distinct from a workspace.

**RBAC** — role-based access control: named roles with permission sets,
assignable to organization members (`api/routers/rbac.py`).

**Resource permission** — a permission scoped to one specific resource
(e.g. one document, one agent) rather than a role-wide grant
(`api/routers/resource_permissions.py`).

**Evaluation Lab** — the platform's evaluation subsystem: datasets,
jobs, results, comparisons between model/prompt/retrieval configurations,
and regression detection. Reused by fine-tuned-model evaluation rather
than duplicated — see [`docs/fine-tuning/EVALUATION.md`](docs/fine-tuning/EVALUATION.md).

**Regression detection** — automatic flagging when a new evaluation run
scores meaningfully worse than a configured baseline
(`api/routers/regression_detection.py`, `regression_thresholds.py`).

**Fine-tuning job** — a request to fine-tune a base model on an uploaded
dataset via a supported provider (OpenAI or Mistral). See
[`docs/fine-tuning/JOBS.md`](docs/fine-tuning/JOBS.md).

**Fine-tuned model** — a model produced by a completed fine-tuning job,
which can be deployed and then used like any other model candidate
(including in the Evaluation Lab).

**Hybrid search** — combining keyword (BM25) and semantic (embedding)
search results via Reciprocal Rank Fusion before reranking. See
[`docs/advanced/RETRIEVAL.md`](docs/advanced/RETRIEVAL.md).

**Reranking** — a cross-encoder pass that re-scores an initial
candidate set for relevance, applied after hybrid search fusion. See
[`docs/advanced/RERANKING.md`](docs/advanced/RERANKING.md).

**Citation** — a reference from a generated answer back to the specific
source document/chunk it was grounded in (`api/routers/citations.py`).

**CLIP visual search** — image-to-image and text-to-image semantic
search over media assets, using OpenAI's CLIP model and a faiss index.
See [`docs/media/SEARCH.md`](docs/media/SEARCH.md).

**Media asset** — an uploaded image, audio, or video file processed by
the media pipeline (vision description, object detection, CLIP
embedding, transcription depending on type).

**A/B test** — an experiment comparing two or more configurations
(prompt, model, retrieval settings) against real usage or evaluation
data. See [`docs/ab-testing/OVERVIEW.md`](docs/ab-testing/OVERVIEW.md).

**White-label** — platform branding hidden or replaced with a
customer's own branding, including custom domains and custom email
domains. See [`docs/whitelabel/CONFIGURATION.md`](docs/whitelabel/CONFIGURATION.md).

**Widget** — the embeddable chat widget that can be dropped into a
third-party site via a script tag. See
[`docs/widget/SCRIPT_TAG.md`](docs/widget/SCRIPT_TAG.md).

**Quota** — a usage limit enforced per organization or plan (e.g.
requests/month, storage), distinct from **rate limiting** (short-window
request throttling).

**Webhook** — an outbound HTTP callback the platform sends on configured
events (`api/routers/webhooks.py`).

**Human approval** — a workflow step that pauses for a human decision
before an agent or automation proceeds (`api/routers/human_approval.py`).

**Plugin** — a third-party extension registered with the platform,
discoverable via the marketplace. See
[`docs/plugins/DEVELOPER_GUIDE.md`](docs/plugins/DEVELOPER_GUIDE.md).

**litellm** — the third-party library this platform uses as its single
abstraction over multiple LLM providers (Anthropic, OpenAI, Mistral,
others), so application code doesn't hardcode provider-specific request
shapes. See [`ARCHITECTURE.md`](ARCHITECTURE.md#llm-access-litellm).
