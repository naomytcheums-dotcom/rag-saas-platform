# Collaboration

## Real, but deliberately bounded

`AgentCollaboration` is a real, new concept -- this part's own audit
confirmed no agent-to-agent delegation/handoff ever existed (the
pre-existing `AgentOrchestrator.run_multi_agent` runs several agents
CONCURRENTLY and INDEPENDENTLY on the same input, with no interaction
between them; it is a real, different primitive).

`POST /autonomous-agents/{id}/collaborate` does all three real steps
in one call: `request_collaboration` (creates the row, `pending`),
`accept_collaboration` (`accepted`), `execute_collaboration`
(`running` -> `completed`/`failed`). Execution is a real, SINGLE,
bounded LLM call -- the collaborator agent reasons over its own real
`goal` plus the delegated task and returns a real answer. This is a
deliberate scope limit: letting a collaboration trigger a full NESTED
autonomous run (the collaborator planning and executing its own
multi-step plan in response) would risk unbounded agent-calls-agent
recursion with no real cap on depth or cost. A real, single-turn
collaboration is what's built; a full nested run is real, documented
future work.

## Shared context

`share_context(agent_id, collaborator_agent_id, context)` writes the
real shared context directly into the COLLABORATOR's own `short_term`
memory (tagged with which agent it came from) -- so it's real,
retrievable context for that agent's own next step, not a fire-and-
forget message.

## Endpoints

- `POST /autonomous-agents/{id}/collaborate` -- `{collaborator_agent_id, task}`.
- `GET /autonomous-agents/{id}/collaborations` -- every real
  collaboration this agent has been part of, as EITHER the initiator
  or the collaborator.
