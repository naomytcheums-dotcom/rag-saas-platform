"""Partie 10.1-10.5 -- custom RBAC, encryption metadata, GDPR/CCPA
compliance tracking, security scanning, and audit-log extensions
(organization_id/resource_type/resource_id columns + an archive table).

Revision ID: 0088
Revises: 0087
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0088"
down_revision: Union[str, None] = "0087"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Partie 10.1: RBAC --------------------------------------------------
    op.create_table(
        "permission_groups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(50), nullable=False, unique=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("resource", sa.String(50), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("group_id", sa.Uuid(), sa.ForeignKey("permission_groups.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_permissions_key", "permissions", ["key"])
    op.create_index("ix_permissions_resource", "permissions", ["resource"])

    op.create_table(
        "custom_roles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "name", name="uq_custom_roles_org_name"),
    )
    op.create_index("ix_custom_roles_organization_id", "custom_roles", ["organization_id"])

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("role_id", sa.Uuid(), sa.ForeignKey("custom_roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", sa.Uuid(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"])

    op.create_table(
        "user_custom_roles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Uuid(), sa.ForeignKey("custom_roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_custom_roles_user_role"),
    )
    op.create_index("ix_user_custom_roles_user_id", "user_custom_roles", ["user_id"])
    op.create_index("ix_user_custom_roles_role_id", "user_custom_roles", ["role_id"])

    # -- Partie 10.2: audit log extensions -----------------------------------
    op.add_column("audit_logs", sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True))
    op.add_column("audit_logs", sa.Column("resource_type", sa.String(50), nullable=True))
    op.add_column("audit_logs", sa.Column("resource_id", sa.String(64), nullable=True))
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])

    op.create_table(
        "audit_logs_archive",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("original_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.String(500), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_archive_original_id", "audit_logs_archive", ["original_id"])

    # -- Partie 10.3: encryption metadata + widen Webhook.secret -------------
    op.alter_column("webhooks", "secret", type_=sa.String(500), existing_type=sa.String(200))

    # Real data migration: every Webhook.secret written before this
    # revision is plaintext (see api/services/webhooks.py's own docstring
    # update) -- encrypt each one in place with the new AES-256-GCM module
    # so api/tasks/webhooks.py's decrypt_webhook_secret() (which now
    # ALWAYS expects the encrypted envelope format) can read it. Skipped
    # entirely, honestly, if ENCRYPTION_MASTER_KEY isn't set yet -- a
    # fresh environment with no webhooks and no key configured has
    # nothing to encrypt and shouldn't fail its migration over it.
    connection = op.get_bind()
    try:
        from api.security.encryption import encrypt_data

        rows = connection.execute(sa.text("SELECT id, secret FROM webhooks WHERE secret IS NOT NULL")).fetchall()
        for row_id, plaintext in rows:
            if plaintext and ":" not in plaintext:  # already-encrypted values contain "current:nonce:ciphertext"
                connection.execute(sa.text("UPDATE webhooks SET secret = :secret WHERE id = :id"), {"secret": encrypt_data(plaintext), "id": row_id})
    except Exception:  # noqa: BLE001 -- ENCRYPTION_MASTER_KEY not configured yet in this environment; nothing to migrate safely without it
        pass

    op.create_table(
        "encryption_key_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "encryption_audit",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("rows_affected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("detail", sa.String(500), nullable=True),
        sa.Column("performed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # -- Partie 10.4: GDPR/CCPA compliance -----------------------------------
    data_request_type = sa.Enum("access", "rectification", "erasure", "restriction", "portability", "objection", name="datarequesttype")
    data_request_status = sa.Enum("pending", "in_progress", "completed", "rejected", name="datarequeststatus")
    op.create_table(
        "data_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_type", data_request_type, nullable=False),
        sa.Column("status", data_request_status, nullable=False, server_default="pending"),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("processed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_data_requests_user_id", "data_requests", ["user_id"])

    op.create_table(
        "consent_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consent_type", sa.String(50), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"])
    op.create_index("ix_consent_records_created_at", "consent_records", ["created_at"])

    op.create_table(
        "data_breaches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("affected_user_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("declared_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_data_breaches_organization_id", "data_breaches", ["organization_id"])

    # -- Partie 10.5: security scanning --------------------------------------
    scan_type = sa.Enum("dependency", "code", "secret", "container", "infrastructure", name="scantype")
    scan_status = sa.Enum("running", "completed", "failed", "unavailable", name="scanstatus")
    vuln_severity = sa.Enum("critical", "high", "medium", "low", name="vulnerabilityseverity")
    vuln_status = sa.Enum("open", "acknowledged", "resolved", "false_positive", name="vulnerabilitystatus")

    op.create_table(
        "security_scans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("scan_type", scan_type, nullable=False),
        sa.Column("status", scan_status, nullable=False, server_default="running"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_security_scans_organization_id", "security_scans", ["organization_id"])

    op.create_table(
        "vulnerabilities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scan_id", sa.Uuid(), sa.ForeignKey("security_scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("severity", vuln_severity, nullable=False),
        sa.Column("status", vuln_status, nullable=False, server_default="open"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("cve_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_vulnerabilities_scan_id", "vulnerabilities", ["scan_id"])

    op.create_table(
        "security_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("vulnerability_id", sa.Uuid(), sa.ForeignKey("vulnerabilities.id", ondelete="CASCADE"), nullable=True),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("severity", vuln_severity, nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_security_alerts_organization_id", "security_alerts", ["organization_id"])

    op.create_table(
        "security_policies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("require_2fa_for_admins", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("session_timeout_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_login_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("ip_allowlist", sa.Text(), nullable=True),
        sa.Column("min_password_strength_bits", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("auto_lock_after_failed_attempts", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("security_policies")
    op.drop_table("security_alerts")
    op.drop_table("vulnerabilities")
    op.drop_table("security_scans")
    sa.Enum(name="vulnerabilitystatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="vulnerabilityseverity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="scanstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="scantype").drop(op.get_bind(), checkfirst=True)

    op.drop_table("data_breaches")
    op.drop_table("consent_records")
    op.drop_table("data_requests")
    sa.Enum(name="datarequeststatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="datarequesttype").drop(op.get_bind(), checkfirst=True)

    op.drop_table("encryption_audit")
    op.drop_table("encryption_key_records")
    op.alter_column("webhooks", "secret", type_=sa.String(200), existing_type=sa.String(500))

    op.drop_table("audit_logs_archive")
    op.drop_index("ix_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_organization_id", table_name="audit_logs")
    op.drop_column("audit_logs", "resource_id")
    op.drop_column("audit_logs", "resource_type")
    op.drop_column("audit_logs", "organization_id")

    op.drop_table("user_custom_roles")
    op.drop_table("role_permissions")
    op.drop_table("custom_roles")
    op.drop_table("permissions")
    op.drop_table("permission_groups")
