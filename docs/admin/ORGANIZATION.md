# Organization

## Creating and configuring an organization

An organization is the top-level multi-tenancy boundary — nearly every
resource (documents, conversations, agents, billing) belongs to exactly
one organization. Configure name, branding, and default settings under
**Admin → Organization**.

## Workspaces

Workspaces group resources inside an organization more narrowly than
the org itself (e.g. per team or per project). Create one under
**Admin → Workspaces** — see `api/routers/workspaces.py`.

## Teams

Teams group members for permission and notification-routing purposes,
distinct from workspaces — see [Teams](TEAMS.md).

## Organization settings

General settings (`api/routers/organization_settings.py`) and branding
(`api/routers/organization_branding.py`) are configured separately from
security/billing settings, which have their own pages — see
[White-label](WHITE_LABEL.md) and [Billing](BILLING.md).

## Deleting an organization

Deletion cascades to all owned resources and cannot be undone. Export
anything you need first.
