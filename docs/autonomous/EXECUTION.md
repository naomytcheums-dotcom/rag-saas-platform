# Execution

## The real loop (`run_autonomous_agent`)

This is the one genuinely new piece every prior 5.1.x/5.3.x docstring
in this codebase explicitly flagged as never having been built. For
each real, still-`pending` step of the agent's own current (or newly
created) plan:

1. **Limit check** (`enforce_limits`) -- if `current_step >= max_steps`
   OR `total_cost >= max_cost` (a real, per-agent `guardrails.max_cost`
   override, else the global `AUTONOMOUS_MAX_COST` default), the agent
   is honestly `paused`, not force-completed or crashed.
2. **Human-approval check** (`human_approval_required`) -- if
   `AUTONOMOUS_HUMAN_APPROVAL` is on and this step's own description
   is in the agent's own `guardrails.require_approval_for` list, the
   agent pauses BEFORE executing. A human resumes it later via the
   SAME real `POST .../resume` endpoint every other pause uses -- no
   separate approval queue was built (a deliberate, documented reuse
   of an existing lifecycle rather than new machinery).
3. **Execute the step** (`execute_step`) -- see below.
4. **Learn** (`learn_from_execution`) -- a real, small episodic memory
   entry recording what happened.
5. **Replan once** if the step failed and a replan hasn't already
   happened this run (see `PLANNING.md`).

When every step is done, the plan and agent are marked
`completed`/`failed` (`error`) honestly based on whether any real step
actually failed.

## One real step (`execute_step`)

1. **Guardrail check** (`check_guardrails`) -- real, BEFORE execution
   (a genuine extension beyond `Agent`'s own guardrails, which today
   only check the final output AFTER a single-turn LLM call). A
   blocked step is marked `failed` with the real violation(s) listed,
   never silently skipped.
2. **Tool selection** (`select_tool`) -- reuses `select_tools` (Partie
   5.1.2's real keyword/LLM ranking) against the real, shared tool
   registry. An honestly empty selection means "no real tool fits."
3. **Either**:
   - a real tool matched: a real, small, COSTED LLM call
     (`_run_costed_completion`) turns the step's free-text description
     into structured parameters matching the tool's own JSON schema,
     then the tool's real `handler` is invoked (`call_tool`).
   - no tool matched: the step is a real reasoning step -- the
     description is sent directly to the LLM via the SAME
     `_run_costed_completion`, and its real response IS the result.
     `action` is recorded as `"respond"`.
4. **Errors never crash the run** (`handle_error`) -- a real tool/LLM
   failure marks the step `failed` with the real error message; the
   loop above decides whether to replan or stop.

## Real cost tracking (`_run_costed_completion`)

Every costed call above uses `chat_completion_with_usage` (Partie
7.2.14) instead of the plain `chat_completion` -- its real,
provider-reported token usage is run through
`api.services.cost_tracking.calculate_cost_per_request` (Partie
7.2.15's own real, static $/M-token pricing table), and the resulting
real USD cost is added to BOTH `step.total_cost` and
`agent.total_cost`. An unpriced model or a provider that doesn't
report usage costs an honest `0` -- never a fabricated estimate, never
a call blocked from completing over a pricing gap.

`GET /autonomous-agents/{id}/cost` returns the real running total, the
real effective cap, whether the agent is currently over budget, and a
real per-step breakdown.

**Honest, documented scope**: `decompose_task` (planning) and
`execute_collaboration`'s own LLM call are NOT costed -- they still
call the plain, unmetered `chat_completion`, a shared function many
OTHER real callers across this codebase depend on; changing its return
shape for cost-tracking's sake alone was out of scope for this
finalization.

## Celery

- `run_autonomous_agent_task` -- dispatched by `POST .../run` and
  `.../resume` (a multi-step plan can involve several real LLM/tool
  calls, too slow for an inline HTTP response).
- `execute_agent_plan_task` -- resolves a plan's own real agent and
  re-drives the same loop.
- `check_agent_guardrails` (hourly) -- any real agent stuck `executing`
  past `AUTONOMOUS_MAX_DURATION` is honestly marked `error`, not left
  silently running forever (a crashed worker, an orphaned run).
