# FAQ — Billing

**Where do I see my current usage?** **Admin → Billing** — see
[Quotas & Limits](../admin/QUOTAS_AND_LIMITS.md).

**What happens if I exceed my quota?** Behavior depends on the
resource — some are hard-capped (request rejected), others allow
overage billing depending on your plan. Check **Admin → Billing → Plan**
for specifics.

**Does self-hosting have platform billing?** Not necessarily — see
[Self-hosted](../install/SELF_HOSTED.md) and
[`docs/sales/SELF_HOSTED.md`](../sales/SELF_HOSTED.md); your agreement
may handle billing outside the platform entirely.

**Are autonomous agent LLM costs billed separately?** Autonomous agent
runs consume real LLM usage tracked in USD
(`AUTONOMOUS_MAX_COST`), which counts toward your organization's usage
the same way any other LLM call does — see
[Autonomous Agents](../advanced/AUTONOMOUS_AGENTS.md#guardrails-and-cost).

**Can I see past invoices?** **Admin → Billing → Invoices** — see
[Billing](../admin/BILLING.md).

**How do partner/white-label billing arrangements work?** See
[`docs/sales/WHITE_LABEL.md`](../sales/WHITE_LABEL.md) and
[`docs/partners/ONBOARDING.md`](../partners/ONBOARDING.md).
