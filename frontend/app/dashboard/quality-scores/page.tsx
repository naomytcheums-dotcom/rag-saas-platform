"use client";

import { useEffect, useState } from "react";
import LoadingState from "@/components/LoadingState";
import { api, ApiError } from "@/lib/api";
import { downloadWithAuth } from "@/lib/download";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

interface Metrics {
  avg_confidence_score: number | null; avg_groundedness_score: number | null; avg_faithfulness_score: number | null; avg_hallucination_score: number | null;
  citation_rate: number; supported_claims_rate: number; contradiction_rate: number; total_responses: number;
}
interface Dashboard { enabled: boolean; metrics: Metrics | null; status_distribution: { low: number; medium: number; high: number } | null }
interface Point { date: string; value: number | null }
interface Item {
  id: string; query: string; answer: string; created_at: string; confidence_score: number | null; groundedness_score: number | null;
  faithfulness_score: number | null; hallucination_score: number | null; has_contradictions: boolean; has_unsupported_claims: boolean;
}

const pct = (value: number | null | undefined) => (value == null ? "—" : `${Math.round(value * 100)} %`);

/** Specs 6.2.12 and 11.2.6: the answer-quality scores (confidence, groundedness, faithfulness, hallucination) in aggregate, over time and per answer.
 * Backed by /organizations/{id}/quality/* (api/routers/quality_dashboard.py). The alert rules stay on /dashboard/quality. */
export default function QualityScoresPage() {
  const { org } = useCurrentOrg();
  const { t } = useTranslation();
  const [days, setDays] = useState(30);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [trend, setTrend] = useState<Point[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!org) return;
    const base = `/organizations/${org.id}/quality`;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with the backend API when the organization or the period changes.
    setLoading(true);
    Promise.all([
      api.get<Dashboard>(`${base}/dashboard?period=${days}`),
      api.get<{ points: Point[] }>(`${base}/trends?period=${days}&metric=groundedness_score`),
      api.get<{ items: Item[] }>(`${base}/responses?limit=25`),
    ])
      .then(([d, tr, r]) => { if (!cancelled) { setDashboard(d); setTrend(tr.points); setItems(r.items); setError(null); } })
      .catch((err) => { if (!cancelled) setError(err instanceof ApiError ? String(err.detail) : t("quality_scores.error_load")); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [org, days, t]);

  const section = "rounded-xl border border-border bg-surface p-4";
  const muted = "text-sm text-foreground-muted";
  const metrics = dashboard?.metrics;
  const cards: [string, number | null | undefined][] = [
    ["quality_scores.confidence", metrics?.avg_confidence_score], ["quality_scores.groundedness", metrics?.avg_groundedness_score],
    ["quality_scores.faithfulness", metrics?.avg_faithfulness_score], ["quality_scores.hallucination", metrics?.avg_hallucination_score],
  ];

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-xl font-semibold text-foreground">{t("quality_scores.title")}</h1>
      <p className="mt-1 text-sm text-foreground-muted">{t("quality_scores.subtitle")}</p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label htmlFor="quality-days" className="text-sm text-foreground-muted">{t("insights.period")}</label>
        <select id="quality-days" value={days} onChange={(e) => setDays(Number(e.target.value))} className="rounded-lg border border-border bg-background px-2 py-1 text-sm">
          {[7, 30, 90, 365].map((d) => <option key={d} value={d}>{d} {t("insights.days")}</option>)}
        </select>
        {org && <button type="button" onClick={() => downloadWithAuth(`/organizations/${org.id}/quality/export?format=csv&period=${days}`, "quality.csv").catch(() => setError(t("quality_scores.error_load")))} className="rounded-lg border border-border px-3 py-1 text-sm text-foreground hover:bg-surface-hover">{t("quality_scores.export")}</button>}
      </div>
      {error && <p role="alert" className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {loading ? <LoadingState fullScreen={false} /> : dashboard && !dashboard.enabled ? (
        <p className={`mt-4 ${section} ${muted}`}>{t("quality_scores.disabled")}</p>
      ) : (
        <>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {cards.map(([key, value]) => (
              <section key={key} className={section}>
                <h2 className="text-sm font-semibold text-foreground">{t(key)}</h2>
                <p className="text-2xl font-semibold text-foreground">{pct(value)}</p>
              </section>
            ))}
          </div>
          <section className={`mt-4 ${section}`}>
            <p className={muted}>
              {metrics?.total_responses ?? 0} {t("quality_scores.responses")} · {t("quality_scores.citation_rate")} {pct(metrics?.citation_rate)} · {t("quality_scores.contradiction_rate")} {pct(metrics?.contradiction_rate)}
              {dashboard?.status_distribution && ` · ${t("quality_scores.low")} ${dashboard.status_distribution.low} / ${t("quality_scores.medium")} ${dashboard.status_distribution.medium} / ${t("quality_scores.high")} ${dashboard.status_distribution.high}`}
            </p>
            <p className={`mt-2 ${muted}`}>{t("quality_scores.trend")}: {trend.length === 0 ? "—" : trend.map((p) => `${p.date.slice(5)} ${pct(p.value)}`).join(" · ")}</p>
          </section>
          <section className={`mt-4 ${section}`}>
            <h2 className="mb-2 text-sm font-semibold text-foreground">{t("quality_scores.per_answer")}</h2>
            {items.length === 0 ? <p className={muted}>{t("insights.empty")}</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-foreground">
                  <thead className="text-foreground-muted"><tr>
                    <th className="py-1 pr-3">{t("quality_scores.question")}</th><th className="pr-3">{t("quality_scores.confidence")}</th><th className="pr-3">{t("quality_scores.groundedness")}</th>
                    <th className="pr-3">{t("quality_scores.faithfulness")}</th><th className="pr-3">{t("quality_scores.hallucination")}</th><th>{t("quality_scores.flags")}</th>
                  </tr></thead>
                  <tbody>
                    {items.map((item) => (
                      <tr key={item.id} className="border-t border-border align-top">
                        <td className="max-w-xs truncate py-1 pr-3" title={item.query}>{item.query}</td>
                        <td className="pr-3">{pct(item.confidence_score)}</td><td className="pr-3">{pct(item.groundedness_score)}</td>
                        <td className="pr-3">{pct(item.faithfulness_score)}</td><td className="pr-3">{pct(item.hallucination_score)}</td>
                        <td>{[item.has_contradictions && t("quality_scores.contradiction"), item.has_unsupported_claims && t("quality_scores.unsupported")].filter(Boolean).join(", ") || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
