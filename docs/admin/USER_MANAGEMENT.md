# User Management

## Organization-level (your org's members)

See [Members & Invitations](MEMBERS_AND_INVITATIONS.md) and
[RBAC](RBAC.md) for day-to-day member management within your own
organization.

## Platform-level (operators only)

If you operate the SaaS platform itself (not just an organization on
it), `api/routers/admin_users.py` and
`api/routers/admin_users_management.py` provide cross-organization user
administration: searching users across all organizations, suspending an
account platform-wide, and impersonation for support purposes (subject
to audit logging — see [Audit Logs](AUDIT_LOGS.md)).

## Deactivating vs. deleting

Deactivating a user blocks login while preserving their content and
history. Deletion is permanent and removes personal data per your
[compliance](COMPLIANCE.md) retention policy.
