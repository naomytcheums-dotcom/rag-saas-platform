"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

interface Rule {
  id: string;
  name: string;
  metric: string;
  operator: "lt" | "lte" | "gt" | "gte";
  threshold: number;
  enabled: boolean;
}

interface HistoryEntry {
  id: string;
  rule_id: string;
  triggered_at: string;
  value_at_trigger: number;
  message: string;
}

interface TestResult {
  current_value: number | null;
  would_trigger: boolean;
}

const OPERATOR_SYMBOL: Record<Rule["operator"], string> = { lt: "<", lte: "≤", gt: ">", gte: "≥" };

export default function QualityAlertsPage() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const { t } = useTranslation();
  const [metrics, setMetrics] = useState<string[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [tests, setTests] = useState<Record<string, TestResult>>({});
  const [name, setName] = useState("");
  const [metric, setMetric] = useState("");
  const [operator, setOperator] = useState<Rule["operator"]>("lt");
  const [threshold, setThreshold] = useState("0.8");
  const [error, setError] = useState<string | null>(null);

  const base = org ? `/organizations/${org.id}/quality-alerts` : null;

  const load = useCallback(async () => {
    if (!base) return;
    try {
      const [metricList, ruleList, historyList] = await Promise.all([
        api.get<{ metrics: string[] }>(`${base}/metrics`),
        api.get<Rule[]>(`${base}/rules`),
        api.get<HistoryEntry[]>(`${base}/history`),
      ]);
      setMetrics(metricList.metrics);
      setMetric((current) => current || metricList.metrics[0] || "");
      setRules(ruleList);
      setHistory(historyList);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("quality.error_generic"));
    }
  }, [base, t]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with the backend API after mount/param change.
    void load();
  }, [load]);

  async function createRule(e: React.FormEvent) {
    e.preventDefault();
    if (!base) return;
    setError(null);
    try {
      await api.post(`${base}/rules`, { name, metric, operator, threshold: Number(threshold) });
      setName("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? JSON.stringify(err.detail) : t("quality.error_generic"));
    }
  }

  async function check(rule: Rule) {
    if (!base) return;
    try {
      const result = await api.post<TestResult>(`${base}/rules/${rule.id}/test`, {});
      setTests((prev) => ({ ...prev, [rule.id]: result }));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("quality.error_generic"));
    }
  }

  async function remove(rule: Rule) {
    if (!base) return;
    try {
      await api.delete(`${base}/rules/${rule.id}`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("quality.error_generic"));
    }
  }

  if (orgLoading || !org) return <p className="p-6">…</p>;

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-2xl font-semibold mb-2">{t("quality.title")}</h1>
      <p className="mb-6 text-sm opacity-80">{t("quality.subtitle")}</p>
      {error && <p role="alert" className="text-danger mb-4">{error}</p>}

      <section className="mb-8">
        <h2 className="font-semibold mb-2">{t("quality.new_rule")}</h2>
        <form onSubmit={createRule} className="grid grid-cols-1 sm:grid-cols-5 gap-2 items-end">
          <label>{t("quality.name")}
            <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full border rounded px-2 py-1" />
          </label>
          <label>{t("quality.metric")}
            <select value={metric} onChange={(e) => setMetric(e.target.value)} className="mt-1 w-full border rounded px-2 py-1">
              {metrics.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
          <label>{t("quality.operator")}
            <select value={operator} onChange={(e) => setOperator(e.target.value as Rule["operator"])} className="mt-1 w-full border rounded px-2 py-1">
              {(Object.keys(OPERATOR_SYMBOL) as Rule["operator"][]).map((op) => <option key={op} value={op}>{OPERATOR_SYMBOL[op]}</option>)}
            </select>
          </label>
          <label>{t("quality.threshold")}
            <input required type="number" min="0" max="1" step="0.01" value={threshold} onChange={(e) => setThreshold(e.target.value)} className="mt-1 w-full border rounded px-2 py-1" />
          </label>
          <button type="submit" className="bg-accent text-white px-3 py-2 rounded">{t("quality.create")}</button>
        </form>
      </section>

      <section className="mb-8">
        <h2 className="font-semibold mb-2">{t("quality.rules")}</h2>
        {rules.length === 0 ? <p className="text-sm">{t("quality.no_rules")}</p> : (
          <ul className="flex flex-col gap-2">
            {rules.map((rule) => {
              const result = tests[rule.id];
              return (
                <li key={rule.id} className="border rounded p-3 flex flex-wrap items-center gap-3">
                  <span className="font-medium">{rule.name}</span>
                  <span className="text-sm">{rule.metric} {OPERATOR_SYMBOL[rule.operator]} {rule.threshold}</span>
                  <button type="button" onClick={() => check(rule)} className="underline text-sm">{t("quality.test")}</button>
                  <button type="button" onClick={() => remove(rule)} className="underline text-sm text-danger">{t("quality.delete")}</button>
                  {result && (
                    <span className="text-sm" aria-live="polite">
                      {t("quality.current_value")}: {result.current_value === null ? t("quality.no_measurement") : result.current_value.toFixed(3)} —{" "}
                      {result.would_trigger ? t("quality.would_trigger") : t("quality.would_not_trigger")}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section>
        <h2 className="font-semibold mb-2">{t("quality.history")}</h2>
        {history.length === 0 ? <p className="text-sm">{t("quality.no_history")}</p> : (
          <ul className="flex flex-col gap-3">
            {history.map((entry) => (
              <li key={entry.id} className="border rounded p-3 text-sm">
                <time className="opacity-70" dateTime={entry.triggered_at}>{new Date(entry.triggered_at).toLocaleString()}</time>
                <p className="mt-1">{entry.message}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
