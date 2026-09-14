# Admin Dashboard

The full admin dashboard build is documented in
[`docs/admin/PARTIE_11_ADMIN_DASHBOARD.md`](PARTIE_11_ADMIN_DASHBOARD.md).
This page is a topical index into it.

## What's in the admin dashboard

- Organization, member, team, and role management — see
  [Organization](ORGANIZATION.md), [Teams](TEAMS.md),
  [Members & Invitations](MEMBERS_AND_INVITATIONS.md), [RBAC](RBAC.md).
- Billing and usage — see [Billing](BILLING.md),
  [Quotas & Limits](QUOTAS_AND_LIMITS.md).
- Security — see [SSO](SSO.md),
  [2FA & WebAuthn](TWO_FACTOR_AND_WEBAUTHN.md),
  [Security Scanning](SECURITY_SCANNING.md), [Audit Logs](AUDIT_LOGS.md),
  [Compliance](COMPLIANCE.md).
- Analytics — usage/business/product/technical dashboards, see
  [`docs/analytics/DASHBOARDS.md`](../analytics/DASHBOARDS.md).
- Quality — the quality dashboard surfaces evaluation results and
  user feedback (see [Feedback](../user/FEEDBACK.md)) so regressions in
  answer quality are visible to admins, not just developers —
  `api/routers/quality_dashboard.py`.
- White-labeling and platform administration — see
  [White-label](WHITE_LABEL.md), [User Management](USER_MANAGEMENT.md).

## Platform-operator admin

The routers under `api/routers/admin_*.py`
(`admin_organizations.py`, `admin_users.py`,
`admin_subscriptions.py`, `admin_users_management.py`) are for platform
operators managing the SaaS itself across organizations — distinct from
an organization admin managing their own org.
