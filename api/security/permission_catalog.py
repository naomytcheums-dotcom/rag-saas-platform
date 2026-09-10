"""
Partie 10.1 -- the fixed, real catalog of granular permissions
(resource:action) a CustomRole can be granted. Fixed in code, not
admin-creatable, for the same reason api/security/organizations.py's
OrganizationRole enum is fixed: a permission this catalog doesn't list
is not something any router actually checks for, so letting an admin
invent one would create a role that LOOKS like it grants something but
grants nothing real.

RESOURCES x ACTIONS = 13 x 4 = 52 permissions. `manage` is deliberately
distinct from (not merely equal to) write+delete -- see
api/services/rbac_custom.py's get_user_effective_permissions for how
`manage` is treated as implying the other three for its own resource.
"""

RESOURCES: list[tuple[str, str]] = [
    ("documents", "Documents"),
    ("agents", "Agents"),
    ("conversations", "Conversations"),
    ("api_keys", "API keys"),
    ("webhooks", "Webhooks"),
    ("widget", "Widget"),
    ("integrations", "Integrations"),
    ("evaluation", "Evaluation"),
    ("billing", "Billing"),
    ("members", "Members"),
    ("settings", "Settings"),
    ("security", "Security"),
    ("audit_logs", "Audit logs"),
]

ACTIONS: list[tuple[str, str]] = [
    ("read", "Read a resource"),
    ("write", "Create or modify a resource"),
    ("delete", "Delete a resource"),
    ("manage", "Fully manage a resource (implies read/write/delete)"),
]


def permission_catalog() -> list[dict]:
    """The full, fixed 52-entry catalog as plain dicts -- one per
    resource x action pair. Pure Python, no DB round-trip: this never
    changes at runtime, so there is nothing to query for."""
    entries = []
    for resource_key, resource_label in RESOURCES:
        for action_key, action_label in ACTIONS:
            entries.append({
                "key": f"{resource_key}:{action_key}",
                "resource": resource_key,
                "resource_label": resource_label,
                "action": action_key,
                "description": f"{action_label} -- {resource_label}",
            })
    return entries


def is_valid_permission_key(key: str) -> bool:
    return any(entry["key"] == key for entry in permission_catalog())
