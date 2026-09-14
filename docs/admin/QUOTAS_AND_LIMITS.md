# Quotas & Limits

## Quotas

A quota is a usage limit tied to your plan (e.g. documents/month, agent
runs/month, storage) — `api/routers/quotas.py`,
`api/routers/user_limits.py`. View current usage against quota under
**Admin → Billing → Usage**.

## Rate limiting

Separate from quotas, rate limiting throttles request bursts over short
windows to protect the platform, regardless of plan — see
[Rate Limiting](../developer/RATE_LIMITING.md) for the developer-facing
detail (HTTP status codes, headers).

## Autonomous agent cost limits

Autonomous agents have their own configurable cost ceiling per run
(`AUTONOMOUS_MAX_COST`) — a real, per-step/per-agent USD tracker that
pauses execution rather than letting a runaway agent accumulate
unbounded LLM spend. See
[`docs/autonomous/OVERVIEW.md`](../autonomous/OVERVIEW.md).

## Upgrading limits

Quotas scale with your subscription plan — see [Billing](BILLING.md).
