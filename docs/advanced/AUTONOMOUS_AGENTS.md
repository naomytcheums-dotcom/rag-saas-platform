# Autonomous Agents

Full documentation: [`docs/autonomous/OVERVIEW.md`](../autonomous/OVERVIEW.md),
[`PLANNING.md`](../autonomous/PLANNING.md), [`EXECUTION.md`](../autonomous/EXECUTION.md),
[`MEMORY.md`](../autonomous/MEMORY.md), [`COLLABORATION.md`](../autonomous/COLLABORATION.md).

## The real difference from a regular agent

A [configured agent](../user/AGENTS.md) responds to one chat turn. An
autonomous agent plans a multi-step goal (`AgentPlan`) and executes it
step by step (`AgentStep`), with a real tool-calling loop — parse the
model's requested tool calls, execute them, feed results back, repeat —
rather than a single LLM call. This was the single most significant
genuine gap closed when autonomous agents were built: every earlier
docstring in the codebase touching agent execution explicitly flagged
that no real multi-step loop existed yet.

## Memory

Autonomous agents can read and write persistent memory across steps
(and, depending on scope, across runs) — `AgentMemory`.

## Collaboration is deliberately bounded

One agent can hand off to another, but this is capped at one real LLM
call per collaboration — not a full nested autonomous sub-run — to
avoid unbounded agent-calls-agent recursion. This is a documented scope
limit, not an oversight.

## Guardrails and cost

Guardrails check content safety before/during execution
(`api/services/agent_guardrails.py`). Cost tracking
(`AUTONOMOUS_MAX_COST`) reuses the platform's real, provider-reported
token usage and pricing table to track USD cost per step and per agent,
pausing execution if a configured ceiling is reached — see
[Quotas & Limits](../admin/QUOTAS_AND_LIMITS.md#autonomous-agent-cost-limits).
