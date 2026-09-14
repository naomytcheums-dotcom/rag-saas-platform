# Rate Limits

Rate limits protect the platform from request bursts, independent of
your plan's usage quotas (see [Quotas & Limits](../admin/QUOTAS_AND_LIMITS.md)
for the plan-level caps).

## Response on limit exceeded

```
HTTP/1.1 429 Too Many Requests
Retry-After: <seconds>
```

```json
{"detail": "Rate limit exceeded"}
```

## Handling 429s

Respect `Retry-After` and back off exponentially on repeated 429s.
Don't retry in a tight loop — this can extend your own throttling
window.

## Scope

Rate limits apply per API key. A burst against one endpoint counts
against your overall limit, not a per-endpoint limit — spreading calls
across different endpoints does not avoid throttling.

## Auth endpoints

Login, password reset, and 2FA endpoints have stricter, dedicated rate
limits as brute-force/spam protection — see
[`docs/AUTH_BACKEND_SETUP.md`](../AUTH_BACKEND_SETUP.md) for the exact
table.

## Geo-adaptive limiting

Some deployments enable geo-adaptive rate limiting (stricter limits
from unexpected regions) — this is an admin/deployment-level
configuration, not something client code needs to account for
differently.
