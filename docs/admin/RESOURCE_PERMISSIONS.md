# Resource Permissions

Resource-level permissions grant access to one specific resource (a
document, an agent, a conversation) rather than a role-wide grant — see
`api/routers/resource_permissions.py`.

## When to use this instead of RBAC

Use [RBAC](RBAC.md) roles for broad, org-wide access patterns. Use
resource permissions when you need an exception: e.g. a contractor who
should only see one project's documents, or a specific agent shared
with one external collaborator.

## Granting a resource permission

From the resource itself (document, agent, etc.), use **Share** or
**Permissions** and add the member or team, with the specific access
level (view/edit/manage).

## Precedence

A resource-level grant is additive to whatever RBAC already allows — it
can grant extra access to a narrower scope, but is not currently used to
restrict access below what a role already grants.
