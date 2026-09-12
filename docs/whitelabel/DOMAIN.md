# White-label custom domain (Partie 19)

Real, honest reuse: `POST/DELETE /organizations/{org_id}/whitelabel/domain`
and `POST .../whitelabel/domain/verify` are a simplified, single-domain
front end over `CustomDomain` (Partie 1.4.1) -- the full multi-domain
CRUD (`/organizations/{org_id}/domains`) still exists unchanged for
callers that need more than one domain per organization; white-label's
own config just shows/manages the organization's single most recent
one, since that's the real, common case for a reseller pointing one
custom domain at their own white-labeled instance.

## Setting a domain

```bash
curl -X POST https://api.yourplatform.example/organizations/{org_id}/whitelabel/domain \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"domain": "app.your-agency.com"}'
```

Returns the full config with `domain` set and `domain_verified: false`.
A malformed hostname, or this platform's own domain, is rejected with a
real `400`.

## Verifying

Add a DNS TXT record at `_rag-saas-verify.<your domain>` (the exact
subdomain and expected token are the same real verification flow
Partie 1.4.1 already built -- see `docs/` for that part's own
documentation of the DNS record shape) pointing at the token this
platform issued, then:

```bash
curl -X POST https://api.yourplatform.example/organizations/{org_id}/whitelabel/domain/verify \
  -H "Authorization: Bearer <token>"
```

This is a real, immediate DNS TXT lookup -- `domain_verified` flips to
`true` the moment it matches, `false` (unchanged, safe to retry) if DNS
hasn't propagated yet. A periodic background sweep (Partie 1.4.4) also
re-checks a still-pending domain automatically, so verifying manually
is a convenience, not the only way it happens.

## Removing

```bash
curl -X DELETE https://api.yourplatform.example/organizations/{org_id}/whitelabel/domain \
  -H "Authorization: Bearer <token>"
```

A real `404` if no domain is currently configured.

## The real domain-detection middleware

Once verified, `api/services/white_label_middleware.py` resolves any
incoming request's `Host` header against this domain on every request,
so future domain-driven (rather than `{org_id}`-in-path) features have
a real, already-working way to know which organization a visitor
arrived through.
