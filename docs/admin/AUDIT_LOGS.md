# Audit Logs

Every sensitive action — role changes, member removal, billing changes,
security setting changes, resource deletions — is recorded in the
organization's audit log (`api/routers/audit.py`).

## Viewing audit logs

**Admin → Security → Audit Log**. Filter by actor, action type, or date
range.

## Retention

Audit log retention is configurable per plan/deployment — check
**Admin → Security → Audit Log settings** for your organization's
current retention window.

## Exporting

Audit logs can be exported for compliance review — see
[Compliance](COMPLIANCE.md).

## Agent traces

Audit logs cover human/admin actions. For a trace of what an autonomous
agent actually did step by step, see agent traces
(`api/routers/agent_traces.py`) and
[`docs/autonomous/EXECUTION.md`](../autonomous/EXECUTION.md).
