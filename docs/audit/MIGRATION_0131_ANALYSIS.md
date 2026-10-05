# Analyse détaillée — migration Alembic 0131 (RLS)

**Analyse statique datée ; l'état de staging (révision 0132, 77 politiques
de laboratoire) est établi dans [STAGING_TEST_REPORT.md](./STAGING_TEST_REPORT.md).**

Analyse statique du fichier local au 2026-10-03. Aucune requête catalogue,
connexion PostgreSQL, migration ou policy n'a été exécutée/créée.

## 1. Contenu complet de `0131_enable_rls_on_remaining_tables.py`

```python
"""Enable RLS on the 11 tables created by migrations 0116-0127 without the
`ENABLE ROW LEVEL SECURITY` line every other table has had since migration
0014, found by `tests/test_postgres_integration.py::test_every_application_table_has_row_level_security_enabled`
failing against the real database during the Hardening Mission regression run.

On Supabase a table without RLS is reachable through the public REST API with the
project's anon key, so this is a real exposure (conversation-adjacent data such as
notifications, retrieval diagnostics, flight recordings, long-term agent memory),
not a style issue. Same remedy as migration 0110: RLS enabled with ZERO policies,
so Postgres' default-deny applies to every non-bypassing role. The application
connects with a role that bypasses RLS and already scopes every query by
organization_id, so no existing query changes behavior.

`IF EXISTS` keeps the migration safe on a database where one of these tables was
never created. Reversible: `downgrade` disables RLS again.

Revision ID: 0131
Revises: 0130
Create Date: 2026-10-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0131"
down_revision: Union[str, None] = "0130"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    "agent_long_term_memory_items",
    "evaluation_failures",
    "flight_recordings",
    "mcp_server_configs",
    "mcp_tool_cache",
    "notification_preferences",
    "notifications",
    "rag_experiments",
    "retrieval_diagnostics",
    "sandbox_environments",
    "workflow_node_executions",
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE IF EXISTS public.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE IF EXISTS public.{table} DISABLE ROW LEVEL SECURITY")
```

## 2. Tables affectées et justification disponible

The migration itself does not encode a per-table justification. Its module
docstring says these eleven tables were created across 0116–0127 and were
missing the RLS enablement expected elsewhere. The functional domain labels
below come from table/model names and ORM ownership, not from a live access
test; where the local source gives no individual rationale, it is marked so.

| Table | Local-domain description | Why included, as verifiable from source |
|---|---|---|
| `agent_long_term_memory_items` | Agent long-term memory entries | Named in `TABLES`; local migration doc says all eleven tables in 0116–0127 had missing RLS; no table-specific rationale in 0131 |
| `evaluation_failures` | Evaluation job failure records | Same migration-level explanation; no per-table reason in 0131 |
| `flight_recordings` | RAG retrieval/generation recording | Table introduced in 0127; migration-level missing-RLS statement |
| `mcp_server_configs` | Tenant MCP server configuration | Migration-level missing-RLS statement; no per-table reason in 0131 |
| `mcp_tool_cache` | MCP discovered tool cache | Migration-level missing-RLS statement; no per-table reason in 0131 |
| `notification_preferences` | Notification settings | Migration-level missing-RLS statement; no per-table reason in 0131 |
| `notifications` | Notification payloads/records | Migration-level missing-RLS statement; docstring calls notifications conversation-adjacent data |
| `rag_experiments` | RAG config experiment history | Table introduced by 0126; migration-level missing-RLS statement |
| `retrieval_diagnostics` | Retrieval diagnostic records | Migration-level missing-RLS statement; docstring calls this conversation-adjacent data |
| `sandbox_environments` | Tool/code sandbox configuration | Migration-level missing-RLS statement; no per-table reason in 0131 |
| `workflow_node_executions` | Workflow node execution state | Migration-level missing-RLS statement; no per-table reason in 0131 |

The SQL applies to all eleven names in `public` when they exist. `IF EXISTS`
does not establish that a table exists, that the statement succeeded on a
target, or what its owner/grants are.

## 3. Why the migration creates no policy

The comments choose “RLS enabled, zero policies” as a boundary: PostgreSQL
default-deny should apply to roles subject to RLS, while the application is
described as using a BYPASSRLS role and application-level organization
filters. This is the repository’s declared design, not a live verification.
Zero policies does **not** implement tenant filtering for a role that
bypasses RLS, and denies ordinary roles unless grants/policies or privileged
access otherwise permit behavior.

## 4. API runtime implications

The source comment claims the app role bypasses RLS. The repository’s
`tests/test_postgres_integration.py` expects `current_user` to have
`rolbypassrls = true` for its configured integration DB. The actual current
role, owner, `rolbypassrls`, grants and destination environment are
**UNKNOWN** because no live query was run. A PostgreSQL superuser or role with
`BYPASSRLS` bypasses RLS; a non-bypass runtime role with no policy sees the
default-deny behavior. No assertion is made about the present deployment.

For a non-bypass API role, these eleven tables lack policies in local
migration source, so legitimate app reads/writes would be denied by RLS
unless operations run under a privileged/owner role. Adding policy-free RLS
does not create organization-specific row access.

## 5. Worker implications

The repository has Celery tasks for media, evaluation, workflows, etc. The
task source imports application database/model/service modules; it is not
enough to prove all worker processes use exactly the same credential string
or connection pool in every deployment. Runtime Celery DB credentials,
role, database target and effective RLS behavior are **UNKNOWN**. If a worker
connects with the same bypass role, RLS does not restrict it; if it uses a
non-bypass role, zero policies can deny task reads/writes.

Before deployment, inspect worker startup/config and verify role at runtime
on a disposable staging database; the connection target is not touched here.

## 6. Alembic implications

The local Alembic environment builds an engine from `settings.DATABASE_URL`
(not the `DATABASE_URL_TRANSACTION` preference used by `api.database.py`).
The migration issues `ALTER TABLE ... ENABLE/DISABLE ROW LEVEL SECURITY`;
the Alembic role therefore needs DDL/table ownership privileges. PostgreSQL
owners/superusers can apply DDL under appropriate privileges. Whether Alembic
can apply this exact revision to the intended database is **UNKNOWN** without
identifying and rehearsing that target. No migration was attempted.

## 7. Platform-admin implications

The platform-admin HTTP role is an application authorization concept and does
not itself imply PostgreSQL `BYPASSRLS`. A platform admin sharing the app
connection would inherit that connection’s DB role. Whether any separate
admin/worker connection exists, its role, and whether it bypasses RLS are
**UNKNOWN**. Do not treat the word “admin” in API code as a DB privilege.

## 8. Local tests versus actual state

The local source says 0131 is revision `0131`, down-revision `0130`, and
contains eleven table names. The locally discovered Alembic graph reached
0131 before the later workspace-description revision was added in this
worktree. The file was untracked at the baseline. A local test source checks
all tables have RLS, zero `pg_policies`, and that the integration role bypasses
RLS; none of those tests was run against the configured DB in this audit.
Therefore:

- **Applied status:** UNKNOWN.
- **RLS state of each named table on target:** UNKNOWN.
- **Policy count on target:** UNKNOWN.
- **API/worker/admin/migration DB role properties:** UNKNOWN.
- **Production REST exposure:** not inferred from comments or local source.

## 9. Correction needed?

Do not blindly add a policy to 0131 or alter this existing local migration.
If tenant-aware RLS is approved, create a new migration only after:

1. identifying an isolated DEV/TEST/STAGING target and its revision/schema;
2. determining runtime, worker, migration and Supabase REST roles/grants;
3. designing transaction-local tenant context and policies for direct,
   indirect, user-owned, global and system tables;
4. testing with a non-owner, non-BYPASSRLS runtime role, two tenants, workers,
   absent tenant context, writes, rollback/commit and PgBouncer transaction
   pooling;
5. validating restore and obtaining deployment approval.

The target policy concepts are documented in
`docs/security/RLS_TARGET_ARCHITECTURE.md` and
`docs/security/RLS_POLICY_DESIGN.md`. No RLS correction is applied by this
analysis.

## 10. Status

**Migration applied: UNKNOWN.** **Migration file present locally:** yes.
**Tracked at the baseline HEAD:** no. **Rows/policies/role checked live:** no.
**Policy change required for the target:** UNKNOWN pending the role, grants,
data classification and intended REST access model. **New migration needed:**
only if an approved target and complete policy design prove a schema change is
required; not decided or executed here.
