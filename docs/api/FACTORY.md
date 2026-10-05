# Agent Factory

Turn a plain-language requirement into a validated agent. Permission: `agents:write`.

```
POST /organizations/{org_id}/factory/blueprint   { "requirement": "...", "name": null }   # dry run, writes nothing
POST /organizations/{org_id}/factory/deploy      { "requirement": "...", "evaluate_dataset_id": null, "min_target_value": null, "target_metric": "recall_at_5" }
```

The blueprint is built by explicit rules (profiles: compliance, support, technical, research, general; English and
French keywords) and carries the `rationale` of every decision. It is validated with the platform's own validators
(retrieval config, tool catalog, memory, guardrails, IDK threshold) and **all** problems are reported together.

`deploy` creates the real agent. With `evaluate_dataset_id` the agent is benchmarked on that dataset (its retrieval
configuration is applied for real); if `min_target_value` is set and the measured `target_metric` is lower — or could
not be measured — the agent is created **paused** and the response says `held_back`. Evaluating costs LLM calls: it
shares the organization's evaluation rate limit and credit / spend-cap pre-flight.
