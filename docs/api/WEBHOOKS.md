# Webhooks API

Backed by `api/routers/webhooks.py`. See
[Webhooks](../developer/WEBHOOKS.md) for the conceptual overview.

## Registering a webhook

```
POST /organizations/{org_id}/webhooks
{
  "url": "https://your-app.example.com/hooks/rag-saas",
  "events": ["document.processed", "conversation.created", "agent_run.completed", "fine_tuning_job.status_changed"]
}
```

## Delivery payload

```json
{
  "event": "document.processed",
  "org_id": "...",
  "resource_id": "...",
  "timestamp": "2026-09-14T12:00:00Z",
  "data": {}
}
```

## Verifying signatures

Each delivery includes a signature header computed with your webhook's
secret (shown once at creation, then only as a masked value). Verify
before trusting the payload — see the specific header name and
algorithm in your instance's [Swagger UI](swagger.md) under
`/webhooks`.

## Retries

Non-2xx responses are retried with backoff for a limited window. Check
delivery history under **Developer settings → Webhooks** if events seem
to be missing — see [Troubleshooting](../install/TROUBLESHOOTING.md).
