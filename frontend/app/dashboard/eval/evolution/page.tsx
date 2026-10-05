"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

interface Dataset { id: string; name: string }
interface Agent { id: string; name: string }

interface Candidate {
  config: Record<string, unknown>;
  job_id: string;
  accepted: boolean;
  target_delta: number | null;
  reasons: string[];
}

interface CycleResult {
  decision: "candidate_recommended" | "baseline_kept";
  target_metric: string;
  recommended_config: Record<string, unknown> | null;
  candidates: Candidate[];
  corpus_constrained: boolean;
}

interface ApplyResult { previous: Record<string, unknown>; current: Record<string, unknown> }

const TARGET_METRICS = ["recall_at_5", "recall_at_10", "mrr", "semantic_similarity"];

function errorText(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
  return fallback;
}

export default function EvolutionPage() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const { t } = useTranslation();
  const [datasets, setDatasets] = useState<Dataset[] | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [targetMetric, setTargetMetric] = useState("recall_at_5");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<CycleResult | null>(null);
  const [agentId, setAgentId] = useState("");
  const [applied, setApplied] = useState<ApplyResult | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!org) return;
    void (async () => {
      try {
        const [datasetPage, agentList] = await Promise.all([
          api.get<{ items: Dataset[] }>(`/organizations/${org.id}/datasets`),
          api.get<Agent[]>(`/organizations/${org.id}/agents`),
        ]);
        setDatasets(datasetPage.items);
        setDatasetId((current) => current || datasetPage.items[0]?.id || "");
        setAgents(agentList);
        setAgentId((current) => current || agentList[0]?.id || "");
      } catch (err) {
        setDatasets([]);
        setError(errorText(err, t("evolution.error_generic")));
      }
    })();
  }, [org, t]);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (!org || !datasetId) return;
    setRunning(true);
    setError(null);
    setNotice(null);
    setApplied(null);
    try {
      setResult(await api.post<CycleResult>(`/organizations/${org.id}/evolution/retrieval/run`, { dataset_id: datasetId, target_metric: targetMetric }));
    } catch (err) {
      setResult(null);
      setError(errorText(err, t("evolution.error_generic")));
    } finally {
      setRunning(false);
    }
  }

  async function apply(config: Record<string, unknown>, replace: boolean) {
    if (!org || !agentId) return;
    setError(null);
    try {
      const outcome = await api.post<ApplyResult>(`/organizations/${org.id}/agents/${agentId}/retrieval-config/apply`, { config, replace });
      setApplied(replace ? null : outcome);
      setNotice(replace ? t("evolution.rolled_back") : t("evolution.applied"));
    } catch (err) {
      setError(errorText(err, t("evolution.error_generic")));
    }
  }

  if (orgLoading || !org) return <p className="p-6">…</p>;

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-2xl font-semibold mb-2">{t("evolution.title")}</h1>
      <p className="mb-6 text-sm opacity-80">{t("evolution.subtitle")}</p>
      {error && <p role="alert" className="text-danger mb-4">{error}</p>}
      {notice && <p role="status" className="mb-4">{notice}</p>}

      {datasets !== null && datasets.length === 0 ? <p>{t("evolution.no_datasets")}</p> : (
        <form onSubmit={run} className="flex flex-wrap gap-3 items-end mb-8">
          <label>{t("evolution.dataset")}
            <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} className="mt-1 block border rounded px-2 py-1">
              {(datasets ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </label>
          <label>{t("evolution.target_metric")}
            <select value={targetMetric} onChange={(e) => setTargetMetric(e.target.value)} className="mt-1 block border rounded px-2 py-1">
              {TARGET_METRICS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
          <button type="submit" disabled={running || !datasetId} className="bg-accent text-white px-4 py-2 rounded disabled:opacity-50">
            {running ? t("evolution.running") : t("evolution.run")}
          </button>
        </form>
      )}

      {result && (
        <section className="mb-8" aria-live="polite">
          <p className="font-medium mb-2">{result.decision === "candidate_recommended" ? t("evolution.decision_recommended") : t("evolution.decision_kept")}</p>
          {result.corpus_constrained && <p className="text-sm mb-2">{t("evolution.corpus_note")}</p>}
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-left border-b">
                <th className="py-1 pr-3">{t("evolution.config")}</th>
                <th className="py-1 pr-3">{result.target_metric} — {t("evolution.delta")}</th>
                <th className="py-1">&nbsp;</th>
              </tr>
            </thead>
            <tbody>
              {result.candidates.map((c) => (
                <tr key={c.job_id} className="border-b align-top">
                  <td className="py-2 pr-3"><code>{JSON.stringify(c.config)}</code></td>
                  <td className="py-2 pr-3">
                    {c.target_delta === null ? "—" : `${c.target_delta >= 0 ? "+" : ""}${c.target_delta.toFixed(3)}`}
                    {c.reasons.length > 0 && <ul className="list-disc pl-4 opacity-80">{c.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
                  </td>
                  <td className="py-2">{c.accepted ? t("evolution.accepted") : t("evolution.rejected")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {result?.recommended_config && (
        <section>
          <h2 className="font-semibold mb-2">{t("evolution.apply_title")}</h2>
          {agents.length === 0 ? <p className="text-sm">{t("evolution.no_agents")}</p> : (
            <div className="flex flex-wrap gap-3 items-end">
              <label>{t("evolution.agent")}
                <select value={agentId} onChange={(e) => { setAgentId(e.target.value); setApplied(null); }} className="mt-1 block border rounded px-2 py-1">
                  {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </label>
              <button type="button" onClick={() => apply(result.recommended_config!, false)} className="bg-accent text-white px-4 py-2 rounded">{t("evolution.apply")}</button>
              {applied && <button type="button" onClick={() => apply(applied.previous, true)} className="border px-4 py-2 rounded">{t("evolution.rollback")}</button>}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
