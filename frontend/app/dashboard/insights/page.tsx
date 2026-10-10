"use client";

import { useEffect, useState } from "react";
import LoadingState from "@/components/LoadingState";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

interface Asked { question: string; count: number }
interface Failed { question: string; reasons: string[] }
interface Gap { suggested_topic: string; times_asked: number; example_questions: string[]; related_documents: string[]; status: string }
interface DocUse { document_id: string; name: string | null; citations: number; average_relevance: number }
interface Success { answered_questions: number; refused: number; success_rate: number | null }
interface UserCost { user_id: string | null; email: string | null; operations: number; credits_spent: number }
interface AnswerCost { credits_spent: number; billed_operations: number; credits_per_operation: number | null }
interface Analysis { negative_feedback: number; by_category: Record<string, number> }

/** Specs 11.2.5, 11.2.7-11.2.10, 11.2.14-11.2.16, 15.2.5: what users ask, where the knowledge base fails them and what to document next.
 * Backed by /organizations/{id}/insights/* and /feedback/analysis (api/routers/insights.py). */
export default function InsightsPage() {
  const { org } = useCurrentOrg();
  const { t } = useTranslation();
  const [days, setDays] = useState(30);
  const [asked, setAsked] = useState<Asked[]>([]);
  const [failed, setFailed] = useState<Failed[]>([]);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [top, setTop] = useState<DocUse[]>([]);
  const [worst, setWorst] = useState<DocUse[]>([]);
  const [success, setSuccess] = useState<Success | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [userCosts, setUserCosts] = useState<UserCost[]>([]);
  const [answerCost, setAnswerCost] = useState<AnswerCost | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!org) return;
    const base = `/organizations/${org.id}`;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with the backend API when the organization or the period changes.
    setLoading(true);
    Promise.all([
      api.get<{ items: Asked[] }>(`${base}/insights/most-asked?days=${days}`),
      api.get<{ items: Failed[] }>(`${base}/insights/failed-questions?days=${days}`),
      api.get<{ items: Gap[] }>(`${base}/insights/documentation-gaps?days=${days}`),
      api.get<{ items: DocUse[] }>(`${base}/insights/documents/top?days=${days}`),
      api.get<{ items: DocUse[] }>(`${base}/insights/documents/worst?days=${days}`),
      api.get<Success>(`${base}/insights/retrieval-success?days=${days}`),
      api.get<Analysis>(`${base}/feedback/analysis`),
      api.get<{ items: UserCost[] }>(`${base}/insights/cost-per-user?days=${days}`),
      api.get<AnswerCost>(`${base}/insights/cost-per-answer?days=${days}`),
    ])
      .then(([a, f, g, tp, w, s, an, uc, ac]) => {
        if (cancelled) return;
        setAsked(a.items); setFailed(f.items); setGaps(g.items); setTop(tp.items); setWorst(w.items); setSuccess(s); setAnalysis(an); setUserCosts(uc.items); setAnswerCost(ac); setError(null);
      })
      .catch((err) => { if (!cancelled) setError(err instanceof ApiError ? String(err.detail) : t("insights.error_load")); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [org, days, t]);

  const section = "rounded-xl border border-border bg-surface p-4";
  const h2 = "mb-2 text-sm font-semibold text-foreground";
  const muted = "text-sm text-foreground-muted";

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-xl font-semibold text-foreground">{t("insights.title")}</h1>
      <p className="mt-1 text-sm text-foreground-muted">{t("insights.subtitle")}</p>
      <div className="mt-4 flex items-center gap-2">
        <label htmlFor="insights-days" className="text-sm text-foreground-muted">{t("insights.period")}</label>
        <select id="insights-days" value={days} onChange={(e) => setDays(Number(e.target.value))} className="rounded-lg border border-border bg-background px-2 py-1 text-sm">
          {[7, 30, 90, 365].map((d) => <option key={d} value={d}>{d} {t("insights.days")}</option>)}
        </select>
      </div>
      {error && <p role="alert" className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {loading ? <LoadingState fullScreen={false} /> : (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <section className={section}>
            <h2 className={h2}>{t("insights.success_rate")}</h2>
            <p className="text-2xl font-semibold text-foreground">{success?.success_rate == null ? "—" : `${Math.round(success.success_rate * 100)} %`}</p>
            <p className={muted}>{success?.answered_questions ?? 0} {t("insights.answered")} · {success?.refused ?? 0} {t("insights.refused")}</p>
            {analysis && <p className={`mt-2 ${muted}`}>{t("insights.negative_feedback")}: {analysis.negative_feedback} {Object.entries(analysis.by_category).map(([k, v]) => `· ${k} ${v}`).join(" ")}</p>}
          </section>
          <section className={section}>
            <h2 className={h2}>{t("insights.most_asked")}</h2>
            {asked.length === 0 ? <p className={muted}>{t("insights.empty")}</p> : <ul className="space-y-1 text-sm text-foreground">{asked.map((a) => <li key={a.question}>{a.question} <span className="text-foreground-muted">×{a.count}</span></li>)}</ul>}
          </section>
          <section className={section}>
            <h2 className={h2}>{t("insights.failed")}</h2>
            {failed.length === 0 ? <p className={muted}>{t("insights.empty")}</p> : <ul className="space-y-1 text-sm text-foreground">{failed.slice(0, 15).map((f, i) => <li key={`${f.question}-${i}`}>{f.question} <span className="text-foreground-muted">({f.reasons.join(", ")})</span></li>)}</ul>}
          </section>
          <section className={section}>
            <h2 className={h2}>{t("insights.doc_gaps")}</h2>
            {gaps.length === 0 ? <p className={muted}>{t("insights.empty")}</p> : (
              <ul className="space-y-2 text-sm text-foreground">
                {gaps.map((g) => (
                  <li key={g.suggested_topic}>
                    <strong>{g.suggested_topic}</strong> <span className="text-foreground-muted">×{g.times_asked} · {t(`insights.status.${g.status}`)}</span>
                    <div className="text-foreground-muted">{g.example_questions.join(" / ")}</div>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className={section}>
            <h2 className={h2}>{t("insights.top_docs")}</h2>
            {top.length === 0 ? <p className={muted}>{t("insights.empty")}</p> : <ul className="space-y-1 text-sm text-foreground">{top.map((d) => <li key={d.document_id}>{d.name ?? d.document_id} <span className="text-foreground-muted">×{d.citations}</span></li>)}</ul>}
          </section>
          <section className={section}>
            <h2 className={h2}>{t("insights.cost")}</h2>
            <p className={muted}>{t("insights.cost_per_answer")}: {answerCost?.credits_per_operation == null ? "—" : answerCost.credits_per_operation} ({answerCost?.credits_spent ?? 0} {t("insights.credits")})</p>
            {userCosts.length === 0 ? <p className={muted}>{t("insights.empty")}</p> : <ul className="mt-2 space-y-1 text-sm text-foreground">{userCosts.map((u) => <li key={u.user_id ?? "none"}>{u.email ?? "—"} <span className="text-foreground-muted">{u.credits_spent} {t("insights.credits")}</span></li>)}</ul>}
          </section>
          <section className={section}>
            <h2 className={h2}>{t("insights.worst_docs")}</h2>
            {worst.length === 0 ? <p className={muted}>{t("insights.empty")}</p> : <ul className="space-y-1 text-sm text-foreground">{worst.map((d) => <li key={d.document_id}>{d.name ?? d.document_id} <span className="text-foreground-muted">{d.average_relevance.toFixed(2)}</span></li>)}</ul>}
          </section>
        </div>
      )}
    </div>
  );
}
