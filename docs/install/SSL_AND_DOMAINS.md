# SSL & Domains

For custom domains and white-label branding, see
[`docs/whitelabel/DOMAIN.md`](../whitelabel/DOMAIN.md) and
[White-label](../admin/WHITE_LABEL.md). This page covers the SSL
mechanics specifically.

## How SSL is provisioned

SSL certificates for custom domains are provisioned via a real ACME
client using the DNS-01 challenge, verified against the Let's Encrypt
staging environment. The private key/certificate material is encrypted
at rest using the platform's shared encryption-at-rest key
(`api/security/encryption.py`) — see `api/routers/ssl_certificates.py`.

## Honest limitation: not fully automatic

DNS-01 requires a DNS TXT record to be created for the challenge. This
platform does not currently integrate with DNS provider APIs
(Cloudflare, Route53, etc.) to create that record automatically — you
create the TXT record manually (or via your own DNS automation) when
prompted, then trigger verification. This is a real, documented gap,
not a bug: full automation would need a DNS-provider integration that
doesn't exist yet.

## Domain verification

Once a domain is added, `api/routers/custom_domains.py` polls
periodically (Celery) to confirm the domain still points at your
deployment and the certificate remains valid, renewing before
expiration.

## Reverse proxy

Serving traffic for an active custom domain by `Host` header requires a
reverse proxy configured to route accordingly — this is part of your
own infrastructure setup, not automated by the platform itself.
