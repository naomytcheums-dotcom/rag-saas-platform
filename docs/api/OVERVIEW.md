# API Reference — Overview

The platform exposes a REST API across 89 routers (`api/routers/`).
Most resources are scoped under an organization:

```
https://your-instance.example.com/organizations/{org_id}/<resource>
```

A few — notably fine-tuning — use flat paths with `org_id` as a
required query parameter instead; see
[`docs/developer/API.md`](../developer/API.md#path-conventions).

## Interactive docs

- [Swagger UI](swagger.md)
- [Redoc](redoc.md)
- [Raw OpenAPI JSON](openapi.json) — generated live from the actual
  FastAPI app, not hand-maintained.

## Reference pages

- [Authentication](AUTHENTICATION.md)
- [Errors](ERRORS.md)
- [Rate Limits](RATE_LIMITS.md)
- [Pagination](PAGINATION.md)
- [Documents](DOCUMENTS.md)
- [Chat](CHAT.md)
- [Agents](AGENTS.md)
- [Webhooks](WEBHOOKS.md)

Not every one of the 89 routers has its own reference page here —
these cover the most commonly integrated-against resources. For
anything else, the live [OpenAPI export](openapi.json) and
[Swagger UI](swagger.md) are authoritative and complete.

## SDKs

If you'd rather not call the REST API directly, see the
[Python](../developer/SDK_PYTHON.md), [JavaScript](../developer/SDK_JS.md),
[React](../developer/SDK_REACT.md), and [Vue](../developer/SDK_VUE.md) SDKs.
