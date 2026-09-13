# Planning

## Real decomposition, reused directly

`create_agent_plan` (`api/services/autonomous_agents.py`) calls
`api.services.task_planning.decompose_task(agent.goal)` -- the SAME
real LLM call every other planning feature in this codebase uses,
asking for a real JSON array of `{"description", "depends_on"}`.
A malformed LLM response degrades to a real, honest single-step plan
wrapping the raw goal -- never raises, never fabricates structure.

## Real validation

`validate_plan` is a thin, real alias of `task_planning.validate_plan`
(checks the global `TASK_PLANNING_MAX_STEPS`, dangling dependencies,
and cycles via Kahn's algorithm). If it fails, the plan is persisted
as `failed` and the agent's own `status` is set to `error` with a
real, readable message -- never silently discarded.

**A plan longer than this agent's own `max_steps` is NOT rejected at
creation** -- a real, deliberate design choice. `enforce_limits`
(checked before every real step in `run_autonomous_agent`, see
`EXECUTION.md`) pauses the agent once the real cap is reached, so an
open-ended goal still makes real, partial progress rather than being
refused outright just because the LLM proposed more steps than the
configured cap.

## Persistence

Each real decomposed step becomes one real `AgentStep` row
(`step_number`, `parameters.description`, `status=pending`). The
`AgentPlan.steps` column keeps the ORIGINAL proposed step list (a real
snapshot) even after a later replan changes which `AgentStep` rows
actually exist -- the plan's own history stays honest.

## Replanning

`replan_if_needed(plan, failed_step)` is real: when a step fails, it
decomposes the goal AGAIN, informed by the real failure (`context`
includes the failed step's own description and error), and replaces
ONLY the still-`pending` remaining steps -- completed steps are never
touched. Bounded to ONE replan attempt per run (`run_autonomous_agent`'s
own `has_replanned` flag) so a persistently failing goal can't loop
forever. A real, invalid replan (fails `validate_plan` itself) is
discarded -- the old, stalled remaining steps stay as the honest
record rather than being replaced with something worse.

## Endpoints

- `GET /autonomous-agents/{id}/plans` -- every real plan this agent
  has ever run, most recent first.
- `GET /autonomous-agents/{id}/plans/{plan_id}` / `.../steps` -- one
  plan's own real detail/steps.
