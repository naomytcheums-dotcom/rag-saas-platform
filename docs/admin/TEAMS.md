# Teams

Teams group organization members for permissions and notification
routing, distinct from [workspaces](ORGANIZATION.md#workspaces) which
group resources.

## Creating a team

**Admin → Teams → New team**. Add members from your organization's
existing member list — see [Members & Invitations](MEMBERS_AND_INVITATIONS.md).

## Team permissions

Teams can be granted roles the same way individual members can — see
[RBAC](RBAC.md). A member's effective permissions are the union of
their individual role and any team roles they inherit.

## Team notifications

Route notifications (approvals, alerts) to a team rather than an
individual — useful for shared inboxes and on-call rotations.
