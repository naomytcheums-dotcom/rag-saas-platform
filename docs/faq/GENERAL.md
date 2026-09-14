# FAQ — General

**What is this platform?** A multi-tenant SaaS platform for building
RAG products — document ingestion, hybrid search, chat with citations,
agents, autonomous agents, workflows, fine-tuning, and more. See the
root [`README.md`](../../README.md).

**How is this different from the `src/` demo?** `src/` is the original
single-tenant, hand-evaluated retrieval demo this platform grew from.
It's a real, honestly-evaluated case study, kept as-is — see
[`src/README.md`](../../src/README.md). The platform (`api/`+`frontend/`)
is the actual product.

**What LLM providers are supported?** Anthropic, OpenAI, Mistral, and
others via [litellm](../../ARCHITECTURE.md#llm-access-litellm) —
configurable per organization/agent.

**Can I self-host?** Yes — see [Self-hosted](../install/SELF_HOSTED.md).

**Is there a free tier?** See [Billing](../admin/BILLING.md) and
[`docs/sales/PRICING.md`](../sales/PRICING.md) for current plans.

**Where do I report a bug or request a feature?** See
[`CONTRIBUTING.md`](../../CONTRIBUTING.md). For security issues, see
[`SECURITY.md`](../../SECURITY.md) instead of a public issue.
