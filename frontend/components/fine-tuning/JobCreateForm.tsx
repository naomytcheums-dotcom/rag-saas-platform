"use client";

import { useState } from "react";
import { useFineTuningDatasets } from "@/lib/hooks/useFineTuningDatasets";
import { useFineTuningJobs } from "@/lib/hooks/useFineTuningJobs";

const PROVIDERS = ["openai", "mistral"];

export function JobCreateForm({ orgId, onCreated }: { orgId: string; onCreated: () => void }) {
  const { datasets } = useFineTuningDatasets(orgId);
  const { create } = useFineTuningJobs(orgId);
  const readyDatasets = datasets.filter((d) => d.status === "ready");

  const [name, setName] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [provider, setProvider] = useState("openai");
  const [baseModel, setBaseModel] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!name.trim() || !datasetId) return;
    setSubmitting(true);
    setError(null);
    try {
      await create({ name, dataset_id: datasetId, provider, base_model: baseModel || undefined });
      setName(""); setDatasetId(""); setBaseModel("");
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Job name" className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
      <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground">
        <option value="">Select a ready dataset…</option>
        {readyDatasets.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.example_count} examples)</option>)}
      </select>
      <select value={provider} onChange={(e) => setProvider(e.target.value)} className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground">
        {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      <input value={baseModel} onChange={(e) => setBaseModel(e.target.value)} placeholder="Base model (optional, defaults to gpt-4o-mini)" className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
      {error && <p className="text-xs text-danger">{error}</p>}
      <button type="button" onClick={() => void submit()} disabled={submitting} className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {submitting ? "Submitting…" : "Start fine-tuning job"}
      </button>
    </div>
  );
}
