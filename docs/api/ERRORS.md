# Errors

FastAPI's standard error shape:

```json
{
  "detail": "A human-readable description of what went wrong"
}
```

Validation errors (`422 Unprocessable Entity`) include per-field detail:

```json
{
  "detail": [
    {"loc": ["body", "email"], "msg": "field required", "type": "value_error.missing"}
  ]
}
```

## Common status codes

| Code | Meaning |
|---|---|
| 400 | Malformed request |
| 401 | Missing or invalid credentials |
| 403 | Authenticated, but not authorized for this resource |
| 404 | Resource not found (or not visible to you — the API does not distinguish, to avoid leaking existence across organizations) |
| 409 | Conflict (e.g. duplicate resource) |
| 422 | Validation error |
| 429 | Rate limited — see [Rate Limits](RATE_LIMITS.md) |
| 5xx | Server error — retry with backoff; if persistent, check [Troubleshooting](../install/TROUBLESHOOTING.md) or your monitoring |

## Provider-specific errors

Some errors originate from an upstream LLM or fine-tuning provider
(Anthropic/OpenAI/Mistral) rather than the platform itself — these are
surfaced with the real provider error message where possible, not
paraphrased or hidden, e.g. a fine-tuning job's `failure_reason` after
it fails at the provider. See
[`docs/fine-tuning/JOBS.md`](../fine-tuning/JOBS.md).

## SDK error types

Client SDKs wrap non-2xx responses in a typed error
(`RagSaasAPIError` / `RagSaasAPIError`) carrying the status code and
`detail` — see [SDKs](../developer/OVERVIEW.md).
