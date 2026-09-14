# Authentication

## API keys

Send your organization's API key as a bearer token:

```
Authorization: Bearer <your-api-key>
```

Create and manage API keys under your organization's developer
settings, or via `api/routers/agent_api_keys.py`. Keys are scoped to
the organization they were created in.

## Widget keys

The embeddable [widget](../developer/WIDGET_EMBED.md) uses a separate
key type (`wgt_...`), scoped for client-side/browser use rather than
server-to-server calls — never use an organization API key in a
browser context.

## Session cookies

The dashboard frontend authenticates members via session cookies set on
login (`api/routers/auth.py`), not API keys — this is for the
first-party dashboard, not third-party integrations.

## Errors

An invalid or missing key returns `401 Unauthorized`. A valid key
without permission for the requested resource returns
`403 Forbidden`. See [Errors](ERRORS.md) for the full error shape.
