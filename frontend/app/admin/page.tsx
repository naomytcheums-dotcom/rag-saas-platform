"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, fileUrl } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

interface AuditLogEntry {
  id: string;
  action: string;
  ip: string | null;
  timestamp: string;
}

type AccessState = "checking" | "granted" | "denied";

const TABS = ["Overview", "Organizations", "Users", "Subscriptions", "Monitoring", "Logs"] as const;
type Tab = (typeof TABS)[number];

export default function AdminPage() {
  const { user, loading } = useRequireAuth();
  const [access, setAccess] = useState<AccessState>("checking");
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("Overview");

  useEffect(() => {
    if (loading || !user) return;
    // Real, server-side authorization -- never a client-side role
    // check. GET /admin/audit-logs is gated by the real require_admin
    // dependency and returns a real 404 (not 403) for a non-admin.
    void api
      .get<{ items: AuditLogEntry[] }>("/admin/audit-logs?limit=1")
      .then(() => setAccess("granted"))
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
        <h1 className="text-lg font-semibold text-foreground">Access restricted</h1>
        <p className="max-w-sm text-sm text-foreground-muted">
          This area is reserved for platform administrators. Your account does not have that role.
        </p>
        {error && <p className="text-xs text-danger">{error}</p>}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <h1 className="text-xl font-semibold text-foreground">Platform admin</h1>
      <p className="mt-1 text-sm text-foreground-muted">Global stats, organizations, users, subscriptions, monitoring, and system logs.</p>

      <div className="mt-5 flex flex-wrap gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm font-medium transition-colors ${
              tab === t ? "border-b-2 border-accent text-accent-hover" : "text-foreground-muted hover:text-foreground"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === "Overview" && <OverviewTab />}
        {tab === "Organizations" && <OrganizationsTab />}
        {tab === "Users" && <UsersTab />}
        {tab === "Subscriptions" && <SubscriptionsTab />}
        {tab === "Monitoring" && <MonitoringTab />}
        {tab === "Logs" && <LogsTab />}
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-xs font-semibold uppercase text-foreground-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold text-foreground">{value}</p>
    </div>
  );
}

function OverviewTab() {
  const [stats, setStats] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.get("/admin/stats").then(setStats).catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to load"));
  }, []);

  if (error) return <p className="text-sm text-danger">{error}</p>;
  if (!stats) return <p className="text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatCard label="Users" value={stats.users.total} />
      <StatCard label="Active users" value={stats.users.active} />
      <StatCard label="Organizations" value={stats.organizations.total} />
      <StatCard label="Active orgs" value={stats.organizations.active} />
      <StatCard label="Documents" value={stats.documents.total} />
      <StatCard label="Agents" value={stats.agents.total} />
      <StatCard label="Conversations" value={stats.conversations.total} />
      <StatCard label="API requests" value={stats.api_usage.total_requests} />
      <StatCard label="MRR" value={`$${(stats.revenue.mrr_cents / 100).toFixed(2)}`} />
      <StatCard label="ARR" value={`$${(stats.revenue.arr_cents / 100).toFixed(2)}`} />
      <StatCard label="Active subs" value={stats.revenue.active_subscriptions} />
      <StatCard label="Churn (30d)" value={stats.revenue.churn_last_30d} />
    </div>
  );
}

function OrganizationsTab() {
  const [orgs, setOrgs] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    void api.get<{ items: any[] }>("/admin/organizations?limit=50").then((r) => setOrgs(r.items)).catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to load"));
  }, []);

  useEffect(() => { load(); }, [load]);

  async function toggleSuspend(org: any) {
    if (org.is_suspended) {
      await api.post(`/admin/organizations/${org.id}/activate`);
    } else {
      const reason = window.prompt("Suspension reason (optional)") ?? undefined;
      await api.post(`/admin/organizations/${org.id}/suspend`, { reason });
    }
    load();
  }

  if (error) return <p className="text-sm text-danger">{error}</p>;

  return (
    <div className="flex flex-col gap-2">
      {orgs.map((org) => (
        <div key={org.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3 text-sm">
          <div>
            <p className="font-medium text-foreground">{org.name}</p>
            <p className="text-xs text-foreground-muted">{org.slug} · {org.is_suspended ? <span className="text-danger">suspended</span> : <span className="text-success">active</span>}</p>
          </div>
          <button type="button" onClick={() => void toggleSuspend(org)} className="text-xs font-medium text-accent hover:underline">
            {org.is_suspended ? "Reactivate" : "Suspend"}
          </button>
        </div>
      ))}
      {orgs.length === 0 && <p className="text-sm text-foreground-muted">No organizations yet.</p>}
    </div>
  );
}

function UsersTab() {
  const [users, setUsers] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const query = search ? `?search=${encodeURIComponent(search)}&limit=50` : "?limit=50";
    void api.get<{ items: any[] }>(`/admin/users${query}`).then((r) => setUsers(r.items)).catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to load"));
  }, [search]);

  useEffect(() => { load(); }, [load]);

  async function toggleSuspend(u: any) {
    if (u.is_active) {
      const reason = window.prompt("Suspension reason (optional)") ?? undefined;
      await api.post(`/admin/users/${u.id}/suspend`, { reason });
    } else {
      await api.post(`/admin/users/${u.id}/activate`);
    }
    load();
  }

  async function resetPassword(u: any) {
    await api.post(`/admin/users/${u.id}/reset-password`);
    window.alert(`Password reset email sent to ${u.email}`);
  }

  if (error) return <p className="text-sm text-danger">{error}</p>;

  return (
    <div>
      <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by email…" className="mb-3 w-full max-w-sm rounded-lg border border-border bg-background px-3 py-2 text-sm" />
      <div className="flex flex-col gap-2">
        {users.map((u) => (
          <div key={u.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3 text-sm">
            <div>
              <p className="font-medium text-foreground">{u.email}</p>
              <p className="text-xs text-foreground-muted">
                {u.role} · {u.is_active ? <span className="text-success">active</span> : <span className="text-danger">suspended</span>} · {u.is_email_verified ? "verified" : "unverified"}
              </p>
            </div>
            <div className="flex gap-3">
              <button type="button" onClick={() => void resetPassword(u)} className="text-xs font-medium text-foreground-muted hover:text-foreground">Reset password</button>
              <button type="button" onClick={() => void toggleSuspend(u)} className="text-xs font-medium text-accent hover:underline">
                {u.is_active ? "Suspend" : "Reactivate"}
              </button>
            </div>
          </div>
        ))}
        {users.length === 0 && <p className="text-sm text-foreground-muted">No users found.</p>}
      </div>
    </div>
  );
}

function SubscriptionsTab() {
  const [plans, setPlans] = useState<any[]>([]);
  const [subs, setSubs] = useState<any[]>([]);
  const [newPlanName, setNewPlanName] = useState("");
  const [newPlanPrice, setNewPlanPrice] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    void api.get<any[]>("/admin/plans").then(setPlans).catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to load"));
    void api.get<any[]>("/admin/subscriptions?limit=50").then(setSubs).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);

  async function createPlan() {
    if (!newPlanName.trim()) return;
    await api.post("/admin/plans", { key: newPlanName.toLowerCase().replace(/\s+/g, "-"), name: newPlanName, monthly_price_cents: Math.round(Number(newPlanPrice || "0") * 100) });
    setNewPlanName("");
    setNewPlanPrice("");
    load();
  }

  if (error) return <p className="text-sm text-danger">{error}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-foreground">Plans</h2>
        <div className="mt-2 flex flex-col gap-1">
          {plans.map((p) => (
            <div key={p.id} className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm">
              <span className="font-medium text-foreground">{p.name}</span>
              <span className="text-foreground-muted">${(p.monthly_price_cents / 100).toFixed(2)}/mo</span>
            </div>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <input value={newPlanName} onChange={(e) => setNewPlanName(e.target.value)} placeholder="Plan name" className="rounded-lg border border-border bg-background px-3 py-2 text-sm" />
          <input value={newPlanPrice} onChange={(e) => setNewPlanPrice(e.target.value)} placeholder="Price/mo ($)" type="number" className="w-32 rounded-lg border border-border bg-background px-3 py-2 text-sm" />
          <button type="button" onClick={() => void createPlan()} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">Create plan</button>
        </div>
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-foreground">Subscriptions</h2>
        <div className="flex flex-col gap-1">
          {subs.map((s) => (
            <div key={s.id} className="flex items-center justify-between rounded-lg border border-border bg-surface px-3 py-2 text-xs">
              <span className="text-foreground-muted">org {s.organization_id.slice(0, 8)}…</span>
              <span className="font-medium text-foreground">{s.status}</span>
            </div>
          ))}
          {subs.length === 0 && <p className="text-sm text-foreground-muted">No subscriptions yet.</p>}
        </div>
      </div>
    </div>
  );
}

function MonitoringTab() {
  const [health, setHealth] = useState<any>(null);
  const [resources, setResources] = useState<any>(null);
  const [queues, setQueues] = useState<any>(null);

  useEffect(() => {
    void api.get("/admin/monitoring/health").then(setHealth).catch(() => {});
    void api.get("/admin/monitoring/resources").then(setResources).catch(() => {});
    void api.get("/admin/monitoring/queues").then(setQueues).catch(() => {});
  }, []);

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Database" value={health?.database ?? "…"} />
        <StatCard label="Redis" value={health?.redis ?? "…"} />
        <StatCard label="Celery" value={health?.celery ?? "…"} />
      </div>
      {resources && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="CPU" value={`${resources.cpu_percent}%`} />
          <StatCard label="Memory" value={`${resources.memory_percent}%`} />
          <StatCard label="Disk" value={`${resources.disk_percent}%`} />
          <StatCard label="CPU cores" value={resources.cpu_count} />
        </div>
      )}
      {queues && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Workers online" value={queues.workers_online} />
          <StatCard label="Active tasks" value={queues.active_tasks} />
          <StatCard label="Scheduled tasks" value={queues.scheduled_tasks} />
          <StatCard label="Reserved tasks" value={queues.reserved_tasks} />
        </div>
      )}
      <div className="rounded-xl border border-border bg-surface p-4">
        <p className="text-xs font-semibold uppercase text-foreground-muted">API documentation</p>
        <a href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/docs`} target="_blank" rel="noreferrer" className="mt-1 block text-sm text-accent hover:underline">
          Open Swagger UI →
        </a>
      </div>
    </div>
  );
}

function LogsTab() {
  const [logs, setLogs] = useState<any[]>([]);
  const [level, setLevel] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const query = level ? `?level=${level}&limit=50` : "?limit=50";
    void api.get<{ items: any[] }>(`/admin/logs${query}`).then((r) => setLogs(r.items)).catch((err) => setError(err instanceof ApiError ? String(err.detail) : "Failed to load"));
  }, [level]);

  useEffect(() => { load(); }, [load]);

  if (error) return <p className="text-sm text-danger">{error}</p>;

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <select value={level} onChange={(e) => setLevel(e.target.value)} className="rounded-lg border border-border bg-background px-2 py-1.5 text-sm">
          <option value="">All levels</option>
          <option value="WARNING">Warning</option>
          <option value="ERROR">Error</option>
          <option value="CRITICAL">Critical</option>
        </select>
        <a href={fileUrl("/admin/logs/export?fmt=csv")} target="_blank" rel="noreferrer" className="text-xs font-medium text-accent hover:underline">Export CSV →</a>
      </div>
      <div className="flex flex-col gap-1">
        {logs.map((log) => (
          <div key={log.id} className="rounded-lg border border-border bg-surface px-3 py-2 text-xs">
            <div className="flex items-center justify-between">
              <span className={`font-medium ${log.level === "ERROR" || log.level === "CRITICAL" ? "text-danger" : "text-warning"}`}>{log.level}</span>
              <span className="text-foreground-muted">{log.logger_name} · {new Date(log.created_at).toLocaleString()}</span>
            </div>
            <p className="mt-1 text-foreground">{log.message}</p>
          </div>
        ))}
        {logs.length === 0 && <p className="text-sm text-foreground-muted">No system logs recorded (real WARNING+ logs are captured live -- this dev process may simply not have logged one yet).</p>}
      </div>
    </div>
  );
}
