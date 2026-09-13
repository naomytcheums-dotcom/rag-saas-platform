# Memory

## Three real, distinct tiers

`AgentMemory.memory_type`: `short_term` (transient working notes),
`long_term` (durable facts, survives consolidation), `episodic` (a
real record of what a specific step/run actually did). Every memory
gets a real embedding (`generate_embeddings`, the same real model
every other search feature in this codebase uses) when
`AUTONOMOUS_MEMORY_ENABLED` is on -- a real embedding failure never
blocks storing the memory's own text (an honest, non-fatal
degradation, same category as OCR/YOLO/CLIP failures elsewhere).

## Real semantic retrieval

`retrieve_relevant_memory(agent_id, query)` embeds the real query and
ranks every real, embedded memory by cosine similarity
(`api.services.retrieval_pipeline.cosine_similarities`, the SAME real
helper Partie 22's own media search reuses) -- not a keyword match, a
real semantic one.

## Consolidation

`consolidate_memory` summarizes EVERY real `short_term` memory into
ONE new `long_term` entry via a real LLM call, then deletes the
consolidated originals. A real, honest no-op (`None`) with fewer than
2 short-term memories -- nothing real to consolidate. Runs daily via
Celery (`consolidate_agent_memory`).

## Forgetting

`forget_old_memory(agent_id, days)` deletes real `short_term` memories
older than `days` -- `long_term` and `episodic` memories are NEVER
auto-forgotten (that's the entire point of the tier distinction). Runs
daily via Celery (`cleanup_old_memory`,
`AUTONOMOUS_MEMORY_RETENTION_DAYS` default 30).

## Endpoints

- `GET /autonomous-agents/{id}/memory?memory_type=...` -- optionally
  filtered.
- `POST /autonomous-agents/{id}/memory` -- add a real memory directly
  (e.g. seeding an agent with known facts before its first run).
- `DELETE /autonomous-agents/{id}/memory/{memory_id}`.
