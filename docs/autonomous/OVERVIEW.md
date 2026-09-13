# Autonomous agents (Partie 23)

Real, honest scope note first: a pre-build audit (this part's own
instructions, item 1) found a real, working single-step Agent chatbot
(Partie 5.3), real task decomposition/validation (Partie 5.1.13), a
real tool registry with real selection (Partie 5.1.2), and real
guardrail primitives (Partie 5.3.9) already built. **Every one of
those modules' own docstrings explicitly flags that no real multi-step
execution loop was ever built** -- that is the one genuine, sizeable
gap this part closes.

## Why `AutonomousAgent` is a new table, not columns on `Agent`

`Agent` (Partie 5.3) is a configured, multi-turn CHATBOT persona: a
`system_prompt`, no `goal`, no run-level status, idles forever between
conversations. `AutonomousAgent` is genuinely different: a single
`goal` it plans and executes toward, then stops. Conflating them would
blur two real, distinct lifecycles. See
`api/models/autonomous_agent.py`'s own module docstring for the full
reasoning.

## What already existed (reused as-is)

- `api.services.task_planning.decompose_task`/`validate_plan` (Partie
  5.1.13) -- real LLM decomposition into ordered, dependency-aware
  steps, real cycle/dangling-dependency validation. Backs
  `create_agent_plan`/`validate_plan` directly.
- `api.services.tool_selection.select_tools` + `api.services.tools`'s
  real `ToolSpec` registry (Partie 5.1.2) -- backs `select_tool`/
  `call_tool` directly. The real, built-in `calculator`/`word_count`
  tools are immediately usable by an autonomous agent's own steps.
- `api.services.agent_guardrails.check_unsafe_content` (made public
  for this reuse) -- the SAME real `_UNSAFE_PATTERNS` regex table
  backs `check_guardrails`/`validate_action`.
- `api.security.documents.generate_embeddings` +
  `api.services.retrieval_pipeline.cosine_similarities` -- back real
  semantic memory retrieval, no new embedding/similarity code.
- `DocumentChunk.embedding`'s plain-JSON-list-of-floats convention --
  reused directly for `AgentMemory.embedding`.

## What Partie 23 adds (the genuine gap)

- **`AutonomousAgent`**: a real, goal-driven entity with a real run
  lifecycle (`idle -> planning -> executing -> completed`/`error`,
  plus `paused`).
- **`AgentPlan`/`AgentStep`**: real, persisted plans and their
  individual steps, each with a real `action` (a resolved tool name,
  or `"respond"` for a pure reasoning step), real `parameters`/
  `result`, and a real per-step status.
- **The real execution loop** (`run_autonomous_agent`): plans, then
  repeatedly selects a tool (or falls back to reasoning), executes it,
  writes the result back, checks guardrails/limits/human-approval
  before each step, and replans once if a step fails. This loop is the
  one thing that never existed anywhere in this codebase before this
  part.
- **`AgentMemory`**: real, tiered (short_term/long_term/episodic)
  memory with real embeddings, real semantic retrieval, real
  consolidation, real forgetting.
- **`AgentCollaboration`**: real agent-to-agent delegation, distinct
  from the pre-existing `run_multi_agent` (which runs agents
  independently, with no interaction between them).

See `PLANNING.md`, `EXECUTION.md`, `MEMORY.md`, and `COLLABORATION.md`
for the real detail on each piece.

## Config

`AUTONOMOUS_AGENTS_ENABLED`, `AUTONOMOUS_MAX_STEPS`,
`AUTONOMOUS_MAX_DURATION`, `AUTONOMOUS_MAX_COST`,
`AUTONOMOUS_MEMORY_ENABLED`, `AUTONOMOUS_MEMORY_RETENTION_DAYS`,
`AUTONOMOUS_COLLABORATION_ENABLED`, `AUTONOMOUS_HUMAN_APPROVAL`
(`api/config.py`). Task-planning/tool-selection settings are unchanged
and reused as-is.

## Cost tracking (finalization) -- real, now enforced

`AUTONOMOUS_MAX_COST` is now real, enforced budget-per-agent, reusing
`api.services.cost_tracking.calculate_cost_per_request` (Partie
7.2.15's own real, static $/M-token pricing table) and
`chat_completion_with_usage` (Partie 7.2.14's own real,
provider-reported token usage) -- no new pricing table, no new
usage-measuring code. `AutonomousAgent.total_cost`/`AgentStep.total_cost`
are real, persisted USD accumulators; `enforce_limits` pauses the
agent once the real total reaches the real cap (a per-agent
`guardrails.max_cost` override, or the global default), the SAME real
pause the `max_steps` cap already uses.

**Honest, documented scope**: only the two real LLM calls
`execute_step` itself makes are costed -- tool-parameter extraction,
and the reasoning "respond" fallback. `decompose_task` (planning) and
`execute_collaboration`'s own LLM call still use the plain, unmetered
`chat_completion` (a shared function used by many OTHER real callers
across this codebase; changing its return shape for their sake was out
of scope). Planning/collaboration cost is a real, narrower, stated gap
-- not silently claimed to be covered. See `EXECUTION.md` for the full
detail and `GET /autonomous-agents/{id}/cost` for the real breakdown.
