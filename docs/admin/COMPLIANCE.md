# Compliance

`api/routers/compliance.py` covers compliance-related tooling: data
export requests, retention policy enforcement, and audit-log export —
see also [Audit Logs](AUDIT_LOGS.md).

## Data export

Members or admins can request an export of an organization's data for
compliance or migration purposes from **Admin → Compliance → Export**.

## Retention policy

Configure how long conversations, documents, and audit logs are
retained before automatic deletion, under **Admin → Compliance →
Retention**.

## Data residency and self-hosting

For deployments with data-residency requirements, self-hosting keeps
all data within your own infrastructure — see
[Self-hosted install](../install/SELF_HOSTED.md).

## Detailed security posture

For the full detail behind these controls (encryption, RLS, audit
coverage), see
[`docs/security/PARTIE_10_SECURITY.md`](../security/PARTIE_10_SECURITY.md).
