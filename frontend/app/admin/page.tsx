"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

interface HealthStatus {
  database: string;
  rate_limit_redis: string;
}

interface AuditLogEntry {
  id: string;
  action: string;
  ip: string | null;
  timestamp: string;
}

type AccessState = "checking" | "granted" | "denied";

export default function AdminPage() {
  const { user, loading } = useRequireAuth();
  const [access, setAccess] = useState<AccessState>("checking");
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (loading || !user) return;
    // Real, server-side authorization -- never a client-side role
    // check. GET /admin/audit-logs is gated by the real
    // require_admin dependency (api/dependencies.py) and returns a
    // real 404 (not 403) for a non-admin, same anti-enumeration
    // convention this whole backend already uses -- a plain member
    // has no way to even confirm this route exists, let alone see
    // its real data.
    void api
      .get<{ items: AuditLogEntry[] }>("/admin/audit-logs?limit=20")
      .then((data) => {
        setLogs(data.items);
        setAccess("granted");
        return api.get<HealthStatus>("/health/ready");
      })
      .then(setHealth)
      .catch((err) => {
        setAccess("denied");
        if (err instanceof ApiError && err.status !== 404) setError(String(err.detail));
      });
  }, [loading, user]);

  if (loading || !user || access === "checking") {
    return <div className="flex h-screen items-center justify-center text-sm text-foreground-muted">Loading…</div>;
  }

  if (access === "denied") {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-2 text-center">
        <span className="text-3xl" aria-hidden="true">🔒</span>
        <h1 className="text-lg font-semibold text-foreground">Access restricted</h1>
        <p className="max-w-sm text-sm text-foreground-muted">
          This area is reserved for platform administrators. Your account does not have that role.
        </p>
        {error && <p className="text-xs text-danger">{error}</p>}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <h1 className="text-xl font-semibold text-foreground">Platform admin</h1>
      <p className="mt-1 text-sm text-foreground-muted">
        Real, honest scope (Partie 11, ~3/34): system health and the real audit log are live below.
        Cross-organization analytics, question clusters, and knowledge-gap detection have no real aggregation
        infrastructure yet.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs font-semibold uppercase text-foreground-muted">Database</p>
          <p className={`mt-1 text-sm font-medium ${health?.database === "ok" ? "text-success" : "text-danger"}`}>
            {health?.database ?? "…"}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs font-semibold uppercase text-foreground-muted">Rate limit (Redis)</p>
          <p className={`mt-1 text-sm font-medium ${health?.rate_limit_redis === "ok" ? "text-success" : "text-danger"}`}>
            {health?.rate_limit_redis ?? "…"}
          </p>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-border bg-surface p-4">
        <p className="text-xs font-semibold uppercase text-foreground-muted">API documentation</p>
        <a href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/docs`} target="_blank" rel="noreferrer" className="mt-1 block text-sm text-accent hover:underline">
          Open Swagger UI →
        </a>
      </div>

      <div className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-foreground">Recent audit log</h2>
        {logs.length === 0 ? (
          <p className="text-sm text-foreground-muted">No entries yet.</p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {logs.map((log) => (
              <div key={log.id} className="flex items-center justify-between rounded-lg border border-border bg-surface px-3 py-2 text-xs">
                <span className="font-medium text-foreground">{log.action}</span>
                <span className="text-foreground-muted">{log.ip ?? "—"} · {new Date(log.timestamp).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
