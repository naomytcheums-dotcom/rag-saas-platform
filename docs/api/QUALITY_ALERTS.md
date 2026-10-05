# Quality alerts (Guardian) and retrieval evolution

All routes need `evaluation:manage` and are scoped to the organization in the path.

## Alerts
```
GET    /organizations/{org_id}/quality-alerts/metrics
GET    /organizations/{org_id}/quality-alerts/rules          POST   .../rules
PATCH  /organizations/{org_id}/quality-alerts/rules/{id}     DELETE .../rules/{id}     POST .../rules/{id}/test
GET    /organizations/{org_id}/quality-alerts/history
GET    /organizations/{org_id}/quality-alerts/channels       POST   .../channels       DELETE .../channels/{id}
```
Only RAG-quality metrics are accepted (`recall_at_1/3/5/10`, `mrr`, `ndcg_at_5`, `hallucination_rate`); each is the
average over the organization's most recent **completed** evaluation job, and `null` when none exists. A fired alert
carries the Autopsy of that job (retrieval / generation / hallucination counts) and the suggested next step.
Channels: email (`{"email": ...}`) or webhook (`{"webhook_url": "https://..."}`, HTTPS only, SSRF-protected at send time).

## Improving retrieval
```
POST /organizations/{org_id}/evolution/retrieval/run                          { "dataset_id": "...", "target_metric": "recall_at_5" }
POST /organizations/{org_id}/agents/{agent_id}/retrieval-config/apply         { "config": {...}, "replace": false }
```
`run` tests several retrieval settings against the same questions and recommends one only if the target metric gains at
least `min_improvement` (default 0.02) **and** no guard metric (recall@5, MRR, NDCG, semantic similarity, hallucination
rate) regresses by more than `max_regression` (default 0.05). Nothing is applied automatically; `apply` is the explicit
step, returns the `previous` configuration, and rolling back is the same call with `config=previous, replace=true`.
