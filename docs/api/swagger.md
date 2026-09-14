# Swagger UI

Every running instance serves interactive Swagger UI at:

```
https://your-instance.example.com/docs
```

This is FastAPI's built-in interactive documentation, generated live
from the actual API — every endpoint, request/response schema, and
"Try it out" execution is against your real instance, not a static
mock.

## Authenticating in Swagger UI

Click **Authorize** and paste your API key (see
[Authentication](AUTHENTICATION.md)) to make authenticated requests
directly from the UI.

## Static export

A point-in-time export of the same schema is committed at
[`docs/api/openapi.json`](openapi.json) for offline reference and for
this documentation's own [API-reference tests](../developer/TESTING.md#documentation-tests)
to validate against. Your running instance's `/docs` is always the
authoritative, up-to-date version.

## Prefer Redoc?

See [Redoc](redoc.md) for a read-focused alternative to Swagger UI's
interactive layout.
