# Technical metrics (Partie 20)

Per-organization, Admin+ -- but read the real scope of each endpoint
carefully, since two of the four are honestly NOT per-organization
data underneath.

## Endpoints

- `GET .../technical/performance` -- thin, honest re-exposure of the
  real Prometheus `REQUEST_DURATION_SECONDS` histogram (via
  `api/services/app_metrics.py`). **Platform-wide, not per-organization**:
  Prometheus's own labels here are method/path/status_class, not
  `org_id` -- there is no way to filter this by organization without
  adding org labels to every HTTP request's own metrics, not done in
  this pass.
- `GET .../technical/errors` -- same real, platform-wide source.
- `GET .../technical/api-usage` -- **this one IS real per-organization
  data**: delegates to the same `OrganizationUsage` ledger
  `product/usage` reads.
- `GET .../technical/llm-usage` -- a real bridge into Evaluation Lab's
  own token/cost tracking (`api/services/token_usage.py`/
  `cost_tracking.py`), aggregated for this organization's own
  `EvaluationDataset` rows. **Honest, disclosed scope**: this covers
  Evaluation Lab runs only. This codebase has no per-production-
  conversation token/cost persistence to aggregate from -- a live chat
  conversation's own real token spend is NOT included here. The
  response's own `"scope": "evaluation_lab_runs_only"` field states
  this explicitly rather than silently implying completeness.
