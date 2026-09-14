# FAQ — Security

**Is my organization's data isolated from other organizations'?** Yes —
enforced at both the application layer and via Postgres row-level
security. See [Multi-tenancy](../advanced/MULTI_TENANCY.md).

**Is data encrypted?** Sensitive data at rest (e.g. stored credentials,
SSL certificate material) uses the platform's shared encryption-at-rest
key. See [`docs/security/PARTIE_10_SECURITY.md`](../security/PARTIE_10_SECURITY.md).

**Do you support SSO?** Yes — see [SSO](../admin/SSO.md).

**Do you support 2FA / hardware security keys?** Yes — see
[2FA & WebAuthn](../admin/TWO_FACTOR_AND_WEBAUTHN.md).

**How do I report a vulnerability?** See [`SECURITY.md`](../../SECURITY.md)
at the repository root — do not open a public issue.

**Is there an audit log?** Yes, for sensitive admin actions — see
[Audit Logs](../admin/AUDIT_LOGS.md). Autonomous agent step-by-step
activity is tracked separately as agent traces.

**How is custom-domain SSL secured?** Via a real ACME client (DNS-01,
verified against Let's Encrypt staging) — see
[SSL & Domains](../install/SSL_AND_DOMAINS.md). Note the DNS-01 step is
manual, not automatic — a real, documented limitation.
