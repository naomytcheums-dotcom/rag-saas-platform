# Authentication

For the initial backend auth setup (sessions, cookies, secrets), see
the existing, authoritative
[`docs/AUTH_BACKEND_SETUP.md`](../AUTH_BACKEND_SETUP.md). This page
summarizes how to authenticate as an API consumer.

## Session auth

The dashboard frontend authenticates via session cookies, set on
login (`api/routers/auth.py`). Not intended for third-party API
consumers — use API keys instead (below).

## API keys

Programmatic and agent access uses API keys
(`api/routers/agent_api_keys.py`). Create one under your organization's
developer settings and send it as a bearer token:

```bash
curl -H "Authorization: Bearer <your-api-key>" \
  https://your-deployment/api/v1/organizations/<org_id>/documents
```

See [API Authentication](../api/AUTHENTICATION.md) for the full
reference.

## OAuth / SSO

For organization member login via OAuth or enterprise SSO, see
[SSO](../admin/SSO.md) — this is about human login, not API-key
programmatic access.

## Two-factor and WebAuthn

Covered in [2FA & WebAuthn](../admin/TWO_FACTOR_AND_WEBAUTHN.md) — these
apply to interactive login, not API keys.
