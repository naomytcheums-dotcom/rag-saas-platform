"use client";

import { Bot, Check, ChevronLeft, ChevronRight, FileText, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { navIcon } from "@/components/dashboard/nav";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

interface DocumentRow { id: string; name: string; file_size: number | null; file_type: string | null; status: string; created_at: string }
interface AgentRow { id: string; name: string; description: string | null; tools?: unknown[] | null; created_at?: string }

const DONE_STATUSES = new Set(["completed", "ready", "indexed"]);

function asList<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) return payload as T[];
  if (payload && typeof payload === "object") {
    const found = Object.values(payload as Record<string, unknown>).find(Array.isArray);
    if (found) return found as T[];
  }
  return [];
}

function extensionOf(name: string, type: string | null): string {
  const fromName = name.includes(".") ? name.split(".").pop() : "";
  const raw = (fromName || type?.split("/").pop() || "file").toLowerCase();
  return raw.length > 5 ? "file" : raw;
}

const EXT_COLORS: Record<string, string> = { pdf: "bg-[#e5372e]", docx: "bg-[#2b6cff]", doc: "bg-[#2b6cff]", txt: "bg-[#6b7280]", md: "bg-[#6b7280]", csv: "bg-[#1f9d55]", json: "bg-[#d99a00]", html: "bg-[#ff4b00]", xml: "bg-[#8b5cf6]", epub: "bg-[#0e9aa7]" };

function formatSize(bytes: number | null): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function Card({ title, action, children, className = "" }: { title: string; action?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-border bg-surface p-5 shadow-sm ${className}`}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-[15px] font-semibold text-foreground">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function MonthCalendar({ language }: { language: string }) {
  const [cursor, setCursor] = useState(() => { const now = new Date(); return new Date(now.getFullYear(), now.getMonth(), 1); });
  const today = new Date();
  const label = new Intl.DateTimeFormat(language, { month: "long", year: "numeric" }).format(cursor);
  const weekdayLabels = Array.from({ length: 7 }, (_, i) => new Intl.DateTimeFormat(language, { weekday: "narrow" }).format(new Date(2024, 0, 7 + i)));
  const firstWeekday = cursor.getDay();
  const days = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
  const cells = [...Array.from({ length: firstWeekday }, () => 0), ...Array.from({ length: days }, (_, i) => i + 1)];
  const isToday = (day: number) => day > 0 && cursor.getFullYear() === today.getFullYear() && cursor.getMonth() === today.getMonth() && day === today.getDate();
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <button type="button" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} aria-label="Previous month" className="rounded p-1 text-foreground-muted hover:bg-surface-muted"><ChevronLeft className="h-4 w-4" aria-hidden /></button>
        <span className="text-xs font-semibold capitalize text-accent">{label}</span>
        <button type="button" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))} aria-label="Next month" className="rounded p-1 text-foreground-muted hover:bg-surface-muted"><ChevronRight className="h-4 w-4" aria-hidden /></button>
      </div>
      <div className="grid grid-cols-7 gap-y-1 text-center text-[10px] uppercase text-foreground-muted/70">{weekdayLabels.map((w, i) => <span key={i}>{w}</span>)}</div>
      <div className="mt-1 grid grid-cols-7 gap-y-1 text-center text-xs text-foreground">
        {cells.map((day, i) => (
          <span key={i} className={`mx-auto grid h-6 w-6 place-items-center rounded-full ${isToday(day) ? "bg-accent font-semibold text-white" : ""}`}>{day || ""}</span>
        ))}
      </div>
    </div>
  );
}

function Gauge({ percent }: { percent: number }) {
  const clamped = Math.max(0, Math.min(100, percent));
  const radius = 70;
  const arc = Math.PI * radius;
  return (
    <svg viewBox="0 0 180 110" className="mx-auto w-full max-w-[220px]" role="img" aria-label={`${clamped}%`}>
      <path d="M 20 95 A 70 70 0 0 1 160 95" fill="none" stroke="#f1e4dc" strokeWidth="14" strokeLinecap="round" />
      <path d="M 20 95 A 70 70 0 0 1 160 95" fill="none" stroke="#ff4b00" strokeWidth="14" strokeLinecap="round" strokeDasharray={`${(arc * clamped) / 100} ${arc}`} />
      <text x="90" y="88" textAnchor="middle" className="fill-foreground text-[26px] font-bold">{clamped}%</text>
    </svg>
  );
}

function monthKey(date: Date): string { return `${date.getFullYear()}-${date.getMonth()}`; }

export default function DashboardHome() {
  const { t, language } = useTranslation();
  const { user } = useAuth();
  const { org } = useCurrentOrg();
  const [documents, setDocuments] = useState<DocumentRow[] | null>(null);
  const [agents, setAgents] = useState<AgentRow[] | null>(null);
  const [keysCount, setKeysCount] = useState<number | null>(null);
  const [hooksCount, setHooksCount] = useState<number | null>(null);

  useEffect(() => {
    if (!org) return;
    void api.get<unknown>(`/organizations/${org.id}/documents`).then((data) => setDocuments(asList<DocumentRow>(data))).catch(() => setDocuments([]));
    void api.get<unknown>(`/organizations/${org.id}/agents`).then((data) => setAgents(asList<AgentRow>(data))).catch(() => setAgents([]));
    void api.get<unknown>(`/organizations/${org.id}/api-keys`).then((data) => setKeysCount(asList(data).length)).catch(() => setKeysCount(0));
    void api.get<unknown>(`/organizations/${org.id}/webhooks`).then((data) => setHooksCount(asList(data).length)).catch(() => setHooksCount(0));
  }, [org]);

  const displayName = (user?.email ?? "").split("@")[0];
  const docs = useMemo(() => documents ?? [], [documents]);
  const indexed = docs.filter((doc) => DONE_STATUSES.has(doc.status)).length;
  const percent = docs.length ? Math.round((indexed / docs.length) * 100) : 0;
  const recentDocs = [...docs].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "")).slice(0, 3);
  const recentAgents = (agents ?? []).slice(0, 2);

  const activity = useMemo(() => {
    const now = new Date();
    const months = Array.from({ length: 5 }, (_, i) => new Date(now.getFullYear(), now.getMonth() - (4 - i), 1));
    const counts = new Map(months.map((month) => [monthKey(month), 0]));
    for (const doc of docs) {
      const created = new Date(doc.created_at);
      if (!Number.isNaN(created.getTime()) && counts.has(monthKey(created))) counts.set(monthKey(created), (counts.get(monthKey(created)) ?? 0) + 1);
    }
    const max = Math.max(1, ...counts.values());
    return months.map((month) => ({ label: new Intl.DateTimeFormat(language, { month: "short" }).format(month), value: counts.get(monthKey(month)) ?? 0, max }));
  }, [docs, language]);

  const todo = [
    { href: "/dashboard/settings/organization", label: t("dash.todo.org"), done: Boolean(org) },
    { href: "/dashboard/documents", label: t("dash.todo.docs"), done: docs.length > 0 },
    { href: "/dashboard/agents/new", label: t("dash.todo.agent"), done: (agents ?? []).length > 0 },
    { href: "/dashboard/settings/api-keys", label: t("dash.todo.key"), done: (keysCount ?? 0) > 0 },
    { href: "/dashboard/settings/webhooks", label: t("dash.todo.hook"), done: (hooksCount ?? 0) > 0 },
  ];

  const quick = [
    { href: "/chat", label: t("nav.chat"), desc: t("dash.quick.chat.desc") },
    { href: "/dashboard/documents", label: t("nav.documents"), desc: t("dash.quick.documents.desc") },
    { href: "/dashboard/agents", label: t("nav.agents"), desc: t("dash.quick.agents.desc") },
    { href: "/dashboard/settings/api-keys", label: t("nav.api_keys"), desc: t("dash.quick.keys.desc") },
    { href: "/dashboard/settings/webhooks", label: t("nav.webhooks"), desc: t("dash.quick.webhooks.desc") },
    { href: "/dashboard/settings/widget", label: t("nav.widget"), desc: t("dash.quick.widget.desc") },
    { href: "/dashboard/settings/integrations", label: t("nav.integrations"), desc: t("dash.quick.integrations.desc") },
    { href: "/dashboard/settings/organization", label: t("nav.organization"), desc: t("dash.quick.organization.desc") },
  ];

  const seeMore = (href: string) => <Link href={href} className="rounded-md bg-accent-soft px-3 py-1 text-xs font-medium text-accent hover:bg-accent-soft-hover">{t("dash.resources.see_more")}</Link>;

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="text-3xl font-bold tracking-tight text-[#211c37]">{t("dashboard.hello")} {displayName} <span aria-hidden>👋🏻</span></h1>
      <p className="mt-1 text-lg text-foreground-muted">{org?.name ? `${org.name} — ` : ""}{t("dash.subtitle")}</p>

      <div className="mt-7 grid grid-cols-1 gap-5 lg:grid-cols-[1fr_1.7fr_0.8fr]">
        <Card title={t("dash.kb.title")}>
          <div className="rounded-md border border-border p-4">
            <span className="grid h-9 w-9 place-items-center rounded-md bg-surface-muted text-foreground"><FileText className="h-5 w-5" aria-hidden /></span>
            <p className="mt-3 text-sm font-semibold text-foreground">{org?.name ?? "…"}</p>
            <div className="mt-3 flex items-center gap-3">
              <div className="h-2 flex-1 rounded-full bg-foreground/5"><div className="h-2 rounded-full bg-accent" style={{ width: `${percent}%` }} /></div>
              <span className="text-xs font-medium text-accent">{indexed}/{docs.length}</span>
            </div>
            <p className="mt-2 text-xs text-foreground-muted">{docs.length ? t("dash.kb.indexed", { done: indexed, total: docs.length }) : t("dash.kb.empty")}</p>
          </div>
        </Card>

        <Card title={t("dash.resources.title")} action={seeMore("/dashboard/documents")}>
          {recentDocs.length === 0 ? (
            <Link href="/dashboard/documents" className="flex items-center gap-3 rounded-md bg-accent-soft px-4 py-3 text-sm font-medium text-accent">{t("dash.resources.upload")} →</Link>
          ) : (
            <ul className="flex flex-col gap-3">
              {recentDocs.map((doc) => {
                const ext = extensionOf(doc.name, doc.file_type);
                return (
                  <li key={doc.id} className="flex items-center gap-3">
                    <span className={`grid h-9 w-8 shrink-0 place-items-center rounded-md text-[9px] font-bold uppercase text-white ${EXT_COLORS[ext] ?? "bg-[#6b7280]"}`}>.{ext}</span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-foreground">{doc.name}</p>
                      <p className="text-xs text-foreground-muted">{doc.status}{doc.file_size ? ` · ${formatSize(doc.file_size)}` : ""}</p>
                    </div>
                    <Link href="/dashboard/documents" className="text-xs font-medium text-accent hover:underline">{t("dash.quick.open")}</Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card title="">
          <MonthCalendar language={language} />
        </Card>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[1.3fr_1fr_1fr]">
        <Card title={t("dash.activity.title")}>
          <div className="mb-3 flex items-center gap-2 text-xs text-foreground-muted"><span className="h-2.5 w-2.5 rounded-sm bg-accent" aria-hidden />{t("dash.activity.legend")}</div>
          <div className="flex h-44 items-end justify-between gap-3 rounded-md border border-border px-5 pb-6 pt-4">
            {activity.map((bar) => (
              <div key={bar.label} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
                <span className="text-[10px] text-foreground-muted">{bar.value}</span>
                <div className="w-full max-w-[34px] rounded-t-md rounded-b-md bg-accent" style={{ height: `${Math.max(4, (bar.value / bar.max) * 100)}%` }} />
                <span className="text-[10px] capitalize text-foreground-muted">{bar.label}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title={t("dash.health.title")}>
          <div className="rounded-md border border-border px-3 py-4">
            <Gauge percent={percent} />
            <p className="mt-1 text-center text-sm text-foreground-muted">{t("dash.health.label")} <strong className="text-foreground">{indexed}/{docs.length}</strong></p>
          </div>
        </Card>

        <Card title={t("dash.todo.title")}>
          <ul className="flex flex-col divide-y divide-border">
            {todo.map((item) => (
              <li key={item.label}>
                <Link href={item.href} className="flex items-center gap-3 py-3">
                  <span className={`grid h-4 w-4 shrink-0 place-items-center rounded-sm border ${item.done ? "border-accent bg-accent text-white" : "border-accent bg-accent-soft"}`}>{item.done && <Check className="h-3 w-3" aria-hidden />}</span>
                  <span className={`text-sm text-foreground ${item.done ? "line-through opacity-60" : ""}`}>{item.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[1.4fr_1fr]">
        <Card title={t("dash.agents.title")} action={<Link href="/dashboard/agents" className="flex items-center gap-2 text-sm font-medium text-foreground-muted hover:text-accent">{t("dash.agents.all")} <Search className="h-4 w-4" aria-hidden /></Link>}>
          {recentAgents.length === 0 ? (
            <Link href="/dashboard/agents/new" className="flex items-center gap-3 rounded-md bg-accent-soft px-4 py-3 text-sm font-medium text-accent">{t("dash.agents.empty")} — {t("dash.agents.create")} →</Link>
          ) : (
            <ul className="flex flex-col gap-3">
              {recentAgents.map((agent, index) => (
                <li key={agent.id}>
                  <Link href={`/dashboard/agents`} className={`flex items-center gap-4 rounded-lg border px-4 py-4 shadow-sm ${index === 0 ? "border-accent" : "border-border"}`}>
                    <span className="grid h-11 w-11 shrink-0 place-items-center rounded-md bg-surface-muted"><Bot className="h-6 w-6 text-foreground" aria-hidden /></span>
                    <div className="min-w-0">
                      <p className={`truncate text-sm font-semibold ${index === 0 ? "text-accent" : "text-foreground"}`}>{agent.name}</p>
                      <p className="truncate text-xs text-foreground-muted">{agent.description || `${(agent.tools ?? []).length} ${t("nav.agents")}`}</p>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title={t("dash.quick.title")}>
          <ul className="flex flex-col gap-2">
            {quick.map((link, index) => {
              const Icon = navIcon(link.href);
              return (
                <li key={link.href}>
                  <Link href={link.href} className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-surface-muted">
                    <Icon className="h-5 w-5 shrink-0 text-foreground" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-foreground">{link.label}</p>
                      <p className="truncate text-xs text-foreground-muted">{link.desc}</p>
                    </div>
                    <span className={`rounded-md px-3 py-1 text-xs font-medium ${index === 0 ? "bg-accent text-white" : "bg-accent-soft text-accent"}`}>{t("dash.quick.open")}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </Card>
      </div>
    </div>
  );
}
