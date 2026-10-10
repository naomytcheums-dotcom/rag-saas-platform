"use client";

import { useCallback, useEffect, useState } from "react";
import LoadingState from "@/components/LoadingState";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

interface Ticket {
  id: string;
  issue: string;
  priority: string;
  status: string;
  resolution: string | null;
  assignee_id: string | null;
  created_at: string;
  sla_due_at: string | null;
  sla_breached: boolean;
}
interface Note { id: string; body: string; created_at: string }

const STATUSES = ["", "open", "assigned", "resolved", "closed"] as const;

/** Spec 15.1.9: the human side of escalations. Lists the organization's tickets (priority, status, SLA), lets staff take a ticket,
 * add internal notes and resolve it with a written resolution. Backed by /organizations/{id}/escalations (api/routers/escalations.py). */
export default function EscalationsPage() {
  const { org } = useCurrentOrg();
  const { t } = useTranslation();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [noteText, setNoteText] = useState("");
  const [resolution, setResolution] = useState("");

  const base = org ? `/organizations/${org.id}/escalations` : null;

  const load = useCallback(async () => {
    if (!base) return;
    setLoading(true);
    try {
      const data = await api.get<{ items: Ticket[] }>(`${base}${filter ? `?status=${filter}` : ""}`);
      setTickets(data.items);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("escalations.error_load"));
    } finally {
      setLoading(false);
    }
  }, [base, filter, t]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with the backend API after mount / filter change.
    void load();
  }, [load]);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("escalations.error_action"));
    }
  }

  async function open(ticket: Ticket) {
    if (openId === ticket.id) { setOpenId(null); return; }
    setOpenId(ticket.id);
    setResolution("");
    setNoteText("");
    try { setNotes(await api.get<Note[]>(`${base}/${ticket.id}/notes`)); } catch { setNotes([]); }
  }

  async function takeTicket(ticket: Ticket) {
    const me = await api.get<{ id: string }>("/account/me");
    await api.post(`${base}/${ticket.id}/assign`, { assignee_id: me.id });
  }

  async function addNote(ticket: Ticket) {
    await api.post(`${base}/${ticket.id}/notes`, { body: noteText });
    setNoteText("");
    setNotes(await api.get<Note[]>(`${base}/${ticket.id}/notes`));
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold text-foreground">{t("escalations.title")}</h1>
      <p className="mt-1 text-sm text-foreground-muted">{t("escalations.subtitle")}</p>
      {error && <p role="alert" className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      <div className="mt-4 flex items-center gap-2">
        <label htmlFor="esc-filter" className="text-sm text-foreground-muted">{t("escalations.filter_status")}</label>
        <select id="esc-filter" value={filter} onChange={(e) => setFilter(e.target.value)} className="rounded-lg border border-border bg-background px-2 py-1 text-sm">
          {STATUSES.map((s) => <option key={s} value={s}>{s === "" ? t("escalations.all") : t(`escalations.status.${s}`)}</option>)}
        </select>
      </div>

      <div className="mt-4 flex flex-col gap-2">
        {loading ? <LoadingState fullScreen={false} /> : tickets.length === 0 ? (
          <p className="text-sm text-foreground-muted">{t("escalations.empty")}</p>
        ) : tickets.map((ticket) => (
          <div key={ticket.id} className="rounded-lg border border-border bg-surface p-3">
            <button type="button" onClick={() => void open(ticket)} className="flex w-full items-start justify-between gap-3 text-left">
              <span className="text-sm font-medium text-foreground">{ticket.issue}</span>
              <span className="shrink-0 text-xs text-foreground-muted">
                {t(`escalations.priority.${ticket.priority}`)} · {t(`escalations.status.${ticket.status}`)}
                {ticket.sla_breached && <strong className="ml-2 text-danger">{t("escalations.sla_breached")}</strong>}
              </span>
            </button>
            {openId === ticket.id && (
              <div className="mt-3 flex flex-col gap-3 border-t border-border pt-3">
                {ticket.sla_due_at && <p className="text-xs text-foreground-muted">{t("escalations.sla_due")} {new Date(ticket.sla_due_at).toLocaleString()}</p>}
                {ticket.resolution && <p className="text-sm text-foreground"><strong>{t("escalations.resolution")}:</strong> {ticket.resolution}</p>}
                <div className="flex flex-wrap gap-2">
                  {ticket.status === "open" && (
                    <button type="button" onClick={() => void run(() => takeTicket(ticket))} className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white">{t("escalations.take")}</button>
                  )}
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-foreground">{t("escalations.notes")}</h3>
                  {notes.length === 0 ? <p className="text-xs text-foreground-muted">{t("escalations.no_notes")}</p> : (
                    <ul className="mt-1 list-disc pl-5 text-sm text-foreground">{notes.map((n) => <li key={n.id}>{n.body}</li>)}</ul>
                  )}
                  <div className="mt-2 flex gap-2">
                    <input value={noteText} onChange={(e) => setNoteText(e.target.value)} aria-label={t("escalations.note_placeholder")} placeholder={t("escalations.note_placeholder")} className="flex-1 rounded-lg border border-border bg-background px-2 py-1 text-sm" />
                    <button type="button" disabled={!noteText.trim()} onClick={() => void run(() => addNote(ticket))} className="rounded-lg border border-border px-3 py-1 text-xs disabled:opacity-50">{t("escalations.add_note")}</button>
                  </div>
                </div>
                {ticket.status !== "resolved" && ticket.status !== "closed" && (
                  <div className="flex gap-2">
                    <input value={resolution} onChange={(e) => setResolution(e.target.value)} aria-label={t("escalations.resolution_placeholder")} placeholder={t("escalations.resolution_placeholder")} className="flex-1 rounded-lg border border-border bg-background px-2 py-1 text-sm" />
                    <button type="button" disabled={!resolution.trim()} onClick={() => void run(() => api.patch(`${base}/${ticket.id}`, { status: "resolved", resolution }))} className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white disabled:opacity-50">{t("escalations.resolve")}</button>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
