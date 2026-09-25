"use client";

import LoadingState from "@/components/LoadingState";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, fileUrl } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";

interface AuditLogEntry {
  id: string;
  action: string;
  ip: string | null;
  timestamp: string;
}

interface AdminStats {
  users: { total: number; active: number };
  organizations: { total: number; active: number };
  documents: { total: number };
  agents: { total: number };
  conversations: { total: number };
  api_usage: { total_requests: number };
  revenue: { mrr_cents: number; arr_cents: number; active_subscriptions: number; churn_last_30d: number };
}

interface AdminOrg {
  id: string;
  name: string;
  slug: string;
  is_suspended: boolean;
}

interface AdminUser {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  is_email_verified: boolean;
}

interface AdminPlan {
  id: string;
  name: string;
  monthly_price_cents: number;
}

interface AdminSubscription {
  id: string;
  organization_id: string;
  status: string;
}

interface HealthStatus {
  database?: string;
  redis?: string;
  celery?: string;
}

interface ResourceStats {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  cpu_count: number;
}

interface QueueStats {
  workers_online: number;
  active_tasks: number;
  scheduled_tasks: number;
  reserved_tasks: number;
}

interface MetricsSummary {
  business: { organizations: number; users: number; conversations: number; active_subscriptions: number };
}

interface TracingStatus {
  active: boolean;
  exporter?: string;
}

interface AlertRule {
  id: string;
  name: string;
  metric: string;
  operator: string;
  threshold: number;
}

interface AlertChannel {
  id: string;
  name: string;
  type: string;
  enabled: boolean;
}

interface AlertHistoryEntry {
  id: string;
  message: string;
}

interface Incident {
  id: string;
  title: string;
  severity: string;
  status: string;
}

interface AdminLogEntry {
  id: string;
  level: string;
  logger_name: string;
  created_at: string;
  message: string;
}

type AccessState = "checking" | "granted" | "denied";

const TABS = ["Overview", "Organizations", "Users", "Subscriptions", "Monitoring", "Logs", "Alerting"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABEL_KEYS: Record<Tab, string> = {
  Overview: "admin.tab_overview",
  Organizations: "admin.tab_orgs",
  Users: "admin.tab_users",
  Subscriptions: "admin.tab_subscriptions",
  Monitoring: "admin.tab_monitoring",
  Logs: "admin.tab_logs",
  Alerting: "admin.tab_alerting",
};

export default function AdminPage() {
  const { user, loading } = useRequireAuth();
  const { t } = useTranslation();
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
    return <LoadingState fullScreen={false} />;
  }

  if (access === "denied") {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-2 text-center">
        <h1 className="text-lg font-semibold text-foreground">{t("admin.access_denied_title")}</h1>
        <p className="max-w-sm text-sm text-foreground-muted">
          Cette section est réservée aux administrateurs de la plateforme. Votre compte n&apos;a pas ce rôle.
        </p>
        {error && <p className="text-xs text-danger">{error}</p>}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <h1 className="text-xl font-semibold text-foreground">{t("admin.title")}</h1>
      <p className="mt-1 text-sm text-foreground-muted">{t("admin.subtitle")}</p>

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
            {t(TAB_LABEL_KEYS[t])}
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
        {tab === "Alerting" && <AlertingTab />}
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
  const { t } = useTranslation();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.get<AdminStats>("/admin/stats").then(setStats).catch((err) => setError(err instanceof ApiError ? String(err.detail) : t("admin.error_load")));
  }, []);

  if (error) return <p className="text-sm text-danger">{error}</p>;
  if (!stats) return <LoadingState fullScreen={false} />;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatCard label={t("admin.users")} value={stats.users.total} />
      <StatCard label={t("admin.active_users")} value={stats.users.active} />
      <StatCard label={t("admin.organizations")} value={stats.organizations.total} />
      <StatCard label={t("admin.active_orgs")} value={stats.organizations.active} />
      <StatCard label={t("admin.documents")} value={stats.documents.total} />
      <StatCard label={t("admin.agents")} value={stats.agents.total} />
      <StatCard label={t("admin.conversations")} value={stats.conversations.total} />
      <StatCard label={t("admin.api_requests")} value={stats.api_usage.total_requests} />
      <StatCard label={t("admin.mrr")} value={`$${(stats.revenue.mrr_cents / 100).toFixed(2)}`} />
      <StatCard label={t("admin.arr")} value={`$${(stats.revenue.arr_cents / 100).toFixed(2)}`} />
      <StatCard label={t("admin.active_subscriptions")} value={stats.revenue.active_subscriptions} />
      <StatCard label={t("admin.churn_30d")} value={stats.revenue.churn_last_30d} />
    </div>
  );
}

function OrganizationsTab() {
  const { t } = useTranslation();
  const [orgs, setOrgs] = useState<AdminOrg[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    void api.get<{ items: AdminOrg[] }>("/admin/organizations?limit=50").then((r) => setOrgs(r.items)).catch((err) => setError(err instanceof ApiError ? String(err.detail) : t("admin.error_load")));
  }, []);

  useEffect(() => { load(); }, [load]);

  async function toggleSuspend(org: AdminOrg) {
    if (org.is_suspended) {
      await api.post(`/admin/organizations/${org.id}/activate`);
    } else {
      const reason = window.prompt(t("admin.suspend_reason")) ?? undefined;
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
            <p className="text-xs text-foreground-muted">{org.slug} · {org.is_suspended ? <span className="text-danger">{t("admin.suspended")}</span> : <span className="text-success">{t("admin.active")}</span>}</p>
          </div>
          <button type="button" onClick={() => void toggleSuspend(org)} className="text-xs font-medium text-accent hover:underline">
            {org.is_suspended ? t("admin.reactivate") : t("admin.suspend")}
          </button>
        </div>
      ))}
      {orgs.length === 0 && <p className="text-sm text-foreground-muted">{t("admin.orgs_empty")}</p>}
    </div>
  );
}

function UsersTab() {
  const { t } = useTranslation();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const query = search ? `?search=${encodeURIComponent(search)}&limit=50` : "?limit=50";
    void api.get<{ items: AdminUser[] }>(`/admin/users${query}`).then((r) => setUsers(r.items)).catch((err) => setError(err instanceof ApiError ? String(err.detail) : t("admin.error_load")));
  }, [search]);

  useEffect(() => { load(); }, [load]);

  async function toggleSuspend(u: AdminUser) {
    if (u.is_active) {
      const reason = window.prompt(t("admin.suspend_reason")) ?? undefined;
      await api.post(`/admin/users/${u.id}/suspend`, { reason });
    } else {
      await api.post(`/admin/users/${u.id}/activate`);
    }
    load();
  }

  async function resetPassword(u: AdminUser) {
    await api.post(`/admin/users/${u.id}/reset-password`);
    window.alert(t("admin.reset_email_sent", { email: u.email }));
  }

  if (error) return <p className="text-sm text-danger">{error}</p>;

  return (
    <div>
      <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t("admin.search_email")} className="mb-3 w-full max-w-sm rounded-lg border border-border bg-background px-3 py-2 text-sm" />
      <div className="flex flex-col gap-2">
        {users.map((u) => (
          <div key={u.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3 text-sm">
            <div>
              <p className="font-medium text-foreground">{u.email}</p>
              <p className="text-xs text-foreground-muted">
                {u.role} · {u.is_active ? <span className="text-success">{t("admin.user_active")}</span> : <span className="text-danger">{t("admin.user_suspended")}</span>} · {u.is_email_verified ? t("admin.user_verified") : t("admin.user_unverified")}
              </p>
            </div>
            <div className="flex gap-3">
              <button type="button" onClick={() => void resetPassword(u)} className="text-xs font-medium text-foreground-muted hover:text-foreground">{t("admin.reset_password")}</button>
              <button type="button" onClick={() => void toggleSuspend(u)} className="text-xs font-medium text-accent hover:underline">
                {u.is_active ? t("admin.suspend") : t("admin.reactivate")}
              </button>
            </div>
          </div>
        ))}
        {users.length === 0 && <p className="text-sm text-foreground-muted">{t("admin.users_empty")}</p>}
      </div>
    </div>
  );
}

function SubscriptionsTab() {
  const { t } = useTranslation();
  const [plans, setPlans] = useState<AdminPlan[]>([]);
  const [subs, setSubs] = useState<AdminSubscription[]>([]);
  const [newPlanName, setNewPlanName] = useState("");
  const [newPlanPrice, setNewPlanPrice] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    void api.get<AdminPlan[]>("/admin/plans").then(setPlans).catch((err) => setError(err instanceof ApiError ? String(err.detail) : t("admin.error_load")));
    void api.get<AdminSubscription[]>("/admin/subscriptions?limit=50").then(setSubs).catch(() => {});
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
        <h2 className="text-sm font-semibold text-foreground">{t("admin.plans")}</h2>
        <div className="mt-2 flex flex-col gap-1">
          {plans.map((p) => (
            <div key={p.id} className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm">
              <span className="font-medium text-foreground">{p.name}</span>
              <span className="text-foreground-muted">${(p.monthly_price_cents / 100).toFixed(2)}{t("admin.plan_monthly")}</span>
            </div>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <input value={newPlanName} onChange={(e) => setNewPlanName(e.target.value)} placeholder={t("admin.plan_name_placeholder")} className="rounded-lg border border-border bg-background px-3 py-2 text-sm" />
          <input value={newPlanPrice} onChange={(e) => setNewPlanPrice(e.target.value)} placeholder={t("admin.plan_price_placeholder")} type="number" className="w-32 rounded-lg border border-border bg-background px-3 py-2 text-sm" />
          <button type="button" onClick={() => void createPlan()} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">{t("admin.create_plan")}</button>
        </div>
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-foreground">{t("admin.subscriptions_heading")}</h2>
        <div className="flex flex-col gap-1">
          {subs.map((s) => (
            <div key={s.id} className="flex items-center justify-between rounded-lg border border-border bg-surface px-3 py-2 text-xs">
              <span className="text-foreground-muted">org {s.organization_id.slice(0, 8)}…</span>
              <span className="font-medium text-foreground">{s.status}</span>
            </div>
          ))}
          {subs.length === 0 && <p className="text-sm text-foreground-muted">{t("admin.subs_empty")}</p>}
        </div>
      </div>
    </div>
  );
}

function MonitoringTab() {
  const { t } = useTranslation();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [resources, setResources] = useState<ResourceStats | null>(null);
  const [queues, setQueues] = useState<QueueStats | null>(null);
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [tracing, setTracing] = useState<TracingStatus | null>(null);

  useEffect(() => {
    void api.get<HealthStatus>("/admin/monitoring/health").then(setHealth).catch(() => {});
    void api.get<ResourceStats>("/admin/monitoring/resources").then(setResources).catch(() => {});
    void api.get<QueueStats>("/admin/monitoring/queues").then(setQueues).catch(() => {});
    void api.get<MetricsSummary>("/monitoring/metrics").then(setMetrics).catch(() => {});
    void api.get<TracingStatus>("/monitoring/tracing/status").then(setTracing).catch(() => {});
  }, []);

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-3 gap-3">
        <StatCard label={t("admin.monitoring_db")} value={health?.database ?? "…"} />
        <StatCard label={t("admin.monitoring_redis")} value={health?.redis ?? "…"} />
        <StatCard label={t("admin.monitoring_celery")} value={health?.celery ?? "…"} />
      </div>
      {resources && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label={t("admin.cpu")} value={`${resources.cpu_percent}%`} />
          <StatCard label={t("admin.memory")} value={`${resources.memory_percent}%`} />
          <StatCard label={t("admin.disk")} value={`${resources.disk_percent}%`} />
          <StatCard label={t("admin.cpu_cores")} value={resources.cpu_count} />
        </div>
      )}
      {queues && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label={t("admin.workers_online")} value={queues.workers_online} />
          <StatCard label={t("admin.active_tasks")} value={queues.active_tasks} />
          <StatCard label={t("admin.scheduled_tasks")} value={queues.scheduled_tasks} />
          <StatCard label={t("admin.reserved_tasks")} value={queues.reserved_tasks} />
        </div>
      )}
      {metrics && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-foreground-muted">{t("admin.business_metrics")}</p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label={t("admin.organizations")} value={metrics.business.organizations} />
            <StatCard label={t("admin.users")} value={metrics.business.users} />
            <StatCard label={t("admin.conversations")} value={metrics.business.conversations} />
            <StatCard label={t("admin.active_subscriptions")} value={metrics.business.active_subscriptions} />
          </div>
        </div>
      )}
      <div className="rounded-xl border border-border bg-surface p-4">
        <p className="text-xs font-semibold uppercase text-foreground-muted">{t("admin.tracing")}</p>
        <p className="mt-1 text-sm text-foreground">
          {tracing ? (tracing.active ? t("admin.tracing_active", { exporter: tracing.exporter ?? "" }) : t("admin.tracing_disabled")) : "…"}
        </p>
      </div>
      <div className="rounded-xl border border-border bg-surface p-4">
        <p className="text-xs font-semibold uppercase text-foreground-muted">{t("admin.api_docs")}</p>
        <a href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/docs`} target="_blank" rel="noreferrer" className="mt-1 block text-sm text-accent hover:underline">
          {t("admin.open_swagger")}
        </a>
        <a href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/metrics`} target="_blank" rel="noreferrer" className="mt-1 block text-sm text-accent hover:underline">
          {t("admin.open_prometheus")}
        </a>
      </div>
    </div>
  );
}

function AlertingTab() {
  const { t } = useTranslation();
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [channels, setChannels] = useState<AlertChannel[]>([]);
  const [history, setHistory] = useState<AlertHistoryEntry[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [newRule, setNewRule] = useState({ name: "", metric: "cpu_percent", operator: "gt", threshold: "80" });
  const [newChannel, setNewChannel] = useState({ name: "", type: "email", value: "" });

  const load = useCallback(() => {
    void api.get<AlertRule[]>("/alerting/rules").then(setRules).catch(() => {});
    void api.get<AlertChannel[]>("/alerting/channels").then(setChannels).catch(() => {});
    void api.get<AlertHistoryEntry[]>("/alerting/history").then(setHistory).catch(() => {});
    void api.get<Incident[]>("/alerting/incidents").then(setIncidents).catch(() => {});
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function createChannel() {
    if (!newChannel.name.trim() || !newChannel.value.trim()) return;
    const config = newChannel.type === "email" ? { email: newChannel.value } : { webhook_url: newChannel.value };
    await api.post("/alerting/channels", { name: newChannel.name, type: newChannel.type, config });
    setNewChannel({ name: "", type: "email", value: "" });
    load();
  }

  async function createRule() {
    if (!newRule.name.trim()) return;
    await api.post("/alerting/rules", { name: newRule.name, metric: newRule.metric, operator: newRule.operator, threshold: Number(newRule.threshold) });
    setNewRule({ name: "", metric: "cpu_percent", operator: "gt", threshold: "80" });
    load();
  }

  async function deleteRule(id: string) {
    await api.delete(`/alerting/rules/${id}`);
    load();
  }

  async function resolveIncident(id: string) {
    await api.post(`/alerting/incidents/${id}/resolve`);
    load();
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="mb-2 text-xs font-semibold uppercase text-foreground-muted">{t("admin.alert_channels")}</p>
        <div className="flex flex-col gap-2">
          {channels.map((c) => (
            <div key={c.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3 text-sm">
              <span>{c.name} ({c.type})</span>
              <span className="text-xs text-foreground-muted">{c.enabled ? t("admin.channel_enabled") : t("admin.channel_disabled")}</span>
            </div>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <input value={newChannel.name} onChange={(e) => setNewChannel({ ...newChannel, name: e.target.value })} placeholder={t("admin.alert_channel_name_placeholder")} className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs outline-none focus:border-accent" />
          <select value={newChannel.type} onChange={(e) => setNewChannel({ ...newChannel, type: e.target.value })} className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs">
            <option value="email">Email</option>
            <option value="webhook">{t("admin.alert_channel_type_webhook")}</option>
          </select>
          <input value={newChannel.value} onChange={(e) => setNewChannel({ ...newChannel, value: e.target.value })} placeholder={newChannel.type === "email" ? "ops@example.com" : "https://hooks..."} className="flex-1 rounded-lg border border-border bg-background px-3 py-1.5 text-xs outline-none focus:border-accent" />
          <button type="button" onClick={() => void createChannel()} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover">{t("admin.add")}</button>
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase text-foreground-muted">{t("admin.alert_rules")}</p>
        <div className="flex flex-col gap-2">
          {rules.map((r) => (
            <div key={r.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3 text-sm">
              <span>{r.name}: {r.metric} {r.operator} {r.threshold}</span>
              <button type="button" onClick={() => void deleteRule(r.id)} className="text-xs font-medium text-danger hover:underline">{t("admin.delete") || "Supprimer"}</button>
            </div>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <input value={newRule.name} onChange={(e) => setNewRule({ ...newRule, name: e.target.value })} placeholder={t("admin.alert_rule_name_placeholder")} className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs outline-none focus:border-accent" />
          <select value={newRule.metric} onChange={(e) => setNewRule({ ...newRule, metric: e.target.value })} className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs">
            <option value="cpu_percent">{t("admin.alert_metric_cpu")}</option>
            <option value="memory_percent">{t("admin.alert_metric_memory")}</option>
            <option value="disk_percent">{t("admin.alert_metric_disk")}</option>
            <option value="celery_queue_backlog">{t("admin.alert_metric_celery_queue")}</option>
            <option value="http_5xx_total">{t("admin.alert_metric_http_5xx")}</option>
          </select>
          <select value={newRule.operator} onChange={(e) => setNewRule({ ...newRule, operator: e.target.value })} className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs">
            <option value="gt">&gt;</option>
            <option value="gte">&ge;</option>
            <option value="lt">&lt;</option>
            <option value="lte">&le;</option>
          </select>
          <input value={newRule.threshold} onChange={(e) => setNewRule({ ...newRule, threshold: e.target.value })} placeholder={t("admin.alert_threshold_placeholder")} className="w-24 rounded-lg border border-border bg-background px-3 py-1.5 text-xs outline-none focus:border-accent" />
          <button type="button" onClick={() => void createRule()} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover">{t("admin.add")}</button>
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase text-foreground-muted">{t("admin.alert_history")}</p>
        {history.length === 0 ? <p className="text-sm text-foreground-muted">{t("admin.alert_history_empty")}</p> : (
          <div className="flex flex-col gap-2">
            {history.map((h) => (
              <div key={h.id} className="rounded-lg border border-border bg-surface p-3 text-sm">{h.message}</div>
            ))}
          </div>
        )}
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase text-foreground-muted">{t("admin.incidents")}</p>
        {incidents.length === 0 ? <p className="text-sm text-foreground-muted">{t("admin.incidents_empty")}</p> : (
          <div className="flex flex-col gap-2">
            {incidents.map((i) => (
              <div key={i.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3 text-sm">
                <span>{i.title} — {i.severity} — {i.status}</span>
                {i.status !== "resolved" && <button type="button" onClick={() => void resolveIncident(i.id)} className="text-xs font-medium text-accent hover:underline">{t("admin.resolve")}</button>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function LogsTab() {
  const { t } = useTranslation();
  const [logs, setLogs] = useState<AdminLogEntry[]>([]);
  const [level, setLevel] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const query = level ? `?level=${level}&limit=50` : "?limit=50";
    void api.get<{ items: AdminLogEntry[] }>(`/admin/logs${query}`).then((r) => setLogs(r.items)).catch((err) => setError(err instanceof ApiError ? String(err.detail) : t("admin.error_load")));
  }, [level]);

  useEffect(() => { load(); }, [load]);

  if (error) return <p className="text-sm text-danger">{error}</p>;

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <select value={level} onChange={(e) => setLevel(e.target.value)} className="rounded-lg border border-border bg-background px-2 py-1.5 text-sm">
          <option value="">{t("admin.all_levels")}</option>
          <option value="WARNING">{t("admin.level_warning")}</option>
          <option value="ERROR">{t("admin.level_error")}</option>
          <option value="CRITICAL">{t("admin.level_critical")}</option>
        </select>
        <a href={fileUrl("/admin/logs/export?fmt=csv")} target="_blank" rel="noreferrer" className="text-xs font-medium text-accent hover:underline">{t("admin.export_csv")}</a>
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
        {logs.length === 0 && <p className="text-sm text-foreground-muted">{t("admin.logs_empty")}</p>}
      </div>
    </div>
  );
}
