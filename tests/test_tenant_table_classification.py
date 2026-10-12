"""Pin the set of tables that no foreign-key chain links to an organization (TEN-006).

A new GLOBAL table must be reviewed on purpose: add it to REVIEWED_GLOBAL_TABLES only after confirming it never holds one organization's data.
"""

import importlib.util
from pathlib import Path

import api.models  # noqa: F401 -- registers every model
from api.database import Base

SCRIPT = Path(__file__).resolve().parents[1] / "audit-reports" / "phase5-2026-10-12" / "tenant_reachability.py"

REVIEWED_GLOBAL_TABLES = {
    "acme_accounts",  # one ACME account for the platform's own TLS certificates
    "agent_memory_items",  # reached only through agent_sessions, whose routes resolve the agent inside the caller's organization
    "encryption_key_records",  # key metadata (labels, active flag), no tenant payload
    "jwt_signing_keys",  # platform signing keys
    "payment_events",  # provider event ids for webhook idempotency, summary only
    "permission_groups",  # catalogue
    "permissions",  # catalogue
    "plans",  # catalogue of offers
    "system_logs",  # platform logs, scrubbed by scripts/scrub_system_logs.py
    "task_plans",  # service-only planner scratch table (api/services/task_planning.py), no HTTP route reads it
    "task_steps",  # child of task_plans
    "users",  # accounts are global, membership links them to organizations
}


def _classify():
    spec = importlib.util.spec_from_file_location("tenant_reachability", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.classify(Base.metadata)


def test_no_unreviewed_global_table():
    global_tables = {name for name, (kind, _) in _classify().items() if kind == "GLOBAL"}
    assert global_tables == REVIEWED_GLOBAL_TABLES, (
        f"new: {sorted(global_tables - REVIEWED_GLOBAL_TABLES)}; no longer global: {sorted(REVIEWED_GLOBAL_TABLES - global_tables)}"
    )


def test_every_table_gets_a_class():
    assert len(_classify()) == len(Base.metadata.tables)
