"""Real, pre-existing gap found via test_postgres_integration.py's own
regression guard (Partie 1.3.5): every migration from 0088 onward (Partie
10 security/compliance, 11 admin dashboard, 12 billing, 13 alerting, 15
integrations, 16 sales models, 16 (ter) plugin marketplace, plus a few
scattered earlier ones) created tables without the
`ALTER TABLE ... ENABLE ROW LEVEL SECURITY` line every earlier migration
had. See docs/AUTH_BACKEND_SETUP.md's Row Level Security section: this is
a defense-in-depth/compliance signal, not functional isolation (the app
connects as `postgres`, which has `rolbypassrls`), so this migration is
purely additive and changes no observable behavior.

Revision ID: 0098
Revises: 0097
Create Date: 2026-09-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0098"
down_revision: Union[str, None] = "0097"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES_MISSING_RLS = [
    "airbyte_connections",
    "alert_channels",
    "alert_history",
    "alert_rules",
    "audit_logs_archive",
    "consent_records",
    "credit_transactions",
    "credits",
    "custom_roles",
    "data_breaches",
    "data_requests",
    "encryption_audit",
    "encryption_key_records",
    "incidents",
    "integration_connections",
    "integration_logs",
    "integration_mappings",
    "invoice_lines",
    "invoices",
    "licenses",
    "permission_groups",
    "permissions",
    "plans",
    "plugin_executions",
    "plugin_installations",
    "plugin_reviews",
    "plugin_versions",
    "plugins",
    "resellers",
    "role_permissions",
    "security_alerts",
    "security_policies",
    "security_scans",
    "sms_messages",
    "stripe_customers",
    "stripe_events",
    "sub_clients",
    "subscriptions",
    "support_ticket_responses",
    "support_tickets",
    "system_logs",
    "usage_alerts",
    "user_custom_roles",
    "vulnerabilities",
]


def upgrade() -> None:
    for table in TABLES_MISSING_RLS:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES_MISSING_RLS:
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
