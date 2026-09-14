# Rate Limiting

Rate limiting throttles request bursts over short windows, independent
of your plan's [quotas](../admin/QUOTAS_AND_LIMITS.md) (which cap
longer-window usage like documents/month).

## Behavior

A request over the limit receives `429 Too Many Requests`. See
[API Rate Limits](../api/RATE_LIMITS.md) for the exact headers and
retry semantics.

## Where it applies

Rate limits apply per API key / per organization, at the API gateway
level, before a request reaches feature-specific logic — so a burst
against one endpoint can affect your limit for others.

## Handling 429s

Respect the `Retry-After` header when present and back off exponentially
on repeated 429s rather than retrying immediately in a tight loop.
