# Multi-tenancy

## The boundary

The organization (`org_id`) is the top-level multi-tenancy boundary.
Nearly every table that stores tenant data carries an `org_id` foreign
key. See [Glossary](../../GLOSSARY.md#organization-org).

## Enforcement — two layers

1. **Application-layer checks** — each feature's `api/security/<feature>.py`
   module verifies the requesting user/API key belongs to the `org_id`
   in the request before any data access.
2. **Row-level security (RLS)** — most tenant-scoped tables additionally
   enable Postgres RLS, so even a query that bypassed the application
   layer (a bug, or a raw admin query) cannot cross tenant boundaries at
   the database level. See
   [`docs/security/PARTIE_10_SECURITY.md`](../security/PARTIE_10_SECURITY.md).

## Sub-org grouping

- **Workspaces** group resources inside an organization.
- **Teams** group members for permissions/notifications.

Neither is a tenancy boundary on its own — both live inside a single
organization's `org_id` scope. See [Organization](../admin/ORGANIZATION.md).

## Retrieval never crosses tenants

Document search, chat context, and agent tool access are all scoped by
`org_id` — an organization's documents are never retrievable by another
organization's queries, regardless of workspace or team structure. See
[Retrieval](RETRIEVAL.md).

## Diagram

See [`docs/diagrams/MULTI_TENANCY.md`](../diagrams/MULTI_TENANCY.md)
for a rendered overview.
