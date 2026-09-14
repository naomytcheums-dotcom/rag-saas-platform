# RBAC (Role-Based Access Control)

## Roles

A role is a named set of permissions, assignable to members or teams.
Manage roles under **Admin → Roles** (`api/routers/rbac.py`).

## Default roles

Most deployments ship with sensible defaults (e.g. Owner, Admin,
Member, Viewer) — check **Admin → Roles** for what's actually
configured in your organization, since role names and permission sets
are customizable.

## Resource-level permissions

RBAC roles are org/workspace-wide. For a permission scoped to one
specific resource (e.g. "this person can edit this one document, but no
others"), see [Resource Permissions](RESOURCE_PERMISSIONS.md) instead.

## Auditing role changes

Role assignment changes are recorded in [Audit Logs](AUDIT_LOGS.md).
