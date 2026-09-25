"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

interface RunComparison {
  run_a: { id: string; name: string; metrics: Record<string, number> };
  run_b: { id: string; name: string; metrics: Record<string, number> };
  diff: { metric: string; a: number; b: number; delta: number }[];
}

export default function RunComparisonPage() {
  const params = useParams();
  const runId = params.runId as string;
  const { t } = useTranslation();
  const [comparison, setComparison] = useState<RunComparison | null>(null);
  const [otherRunId, setOtherRunId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadComparison(withRunId: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<RunComparison>(`/jobs/${runId}/comparison?with=${withRunId}`);
      setComparison(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("eval_comparison.error_generic"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-4">{t("eval_comparison.title")}</h1>
      <div className="mb-4 flex gap-2">
        <input type="text" value={otherRunId} onChange={(e) => setOtherRunId(e.target.value)} placeholder={t("eval_comparison.run_id_placeholder")} className="border rounded px-3 py-2 flex-1" />
        <button onClick={() => loadComparison(otherRunId)} disabled={!otherRunId || loading} className="bg-accent text-white px-4 py-2 rounded disabled:opacity-50">{loading ? t("eval_comparison.loading") : t("eval_comparison.compare")}</button>
      </div>
      {error && <p className="text-danger mb-4">{error}</p>}
      {comparison && (
        <table className="w-full border">
          <thead>
            <tr className="bg-gray-100">
              <th className="border p-2">{t("eval_comparison.metric")}</th>
              <th className="border p-2">{comparison.run_a.name}</th>
              <th className="border p-2">{comparison.run_b.name}</th>
              <th className="border p-2">{t("eval_comparison.delta")}</th>
            </tr>
          </thead>
          <tbody>
            {comparison.diff.map((row) => (
              <tr key={row.metric}>
                <td className="border p-2">{row.metric}</td>
                <td className="border p-2">{row.a.toFixed(3)}</td>
                <td className="border p-2">{row.b.toFixed(3)}</td>
                <td className={`border p-2 ${row.delta > 0 ? "text-green-600" : row.delta < 0 ? "text-red-600" : ""}`}>{row.delta > 0 ? "+" : ""}{row.delta.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
