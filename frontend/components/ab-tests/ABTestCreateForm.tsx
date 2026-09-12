"use client";

import { useState } from "react";
import { ABTestTrafficSplit } from "@/components/ab-tests/ABTestTrafficSplit";
import { ABTestVariantSelector } from "@/components/ab-tests/ABTestVariantSelector";
import { useABTests } from "@/lib/hooks/useABTests";

const TEST_TYPES = ["agent", "prompt", "model"] as const;
const TARGET_METRICS = ["conversion_rate", "user_satisfaction", "task_completion_rate", "avg_response_time", "error_rate", "retention_rate"];

interface ABTestCreateFormProps {
  orgId: string;
  onCreated?: () => void;
}

export function ABTestCreateForm({ orgId, onCreated }: ABTestCreateFormProps) {
  const { create } = useABTests(orgId);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [variantA, setVariantA] = useState("");
  const [variantB, setVariantB] = useState("");
  const [trafficSplit, setTrafficSplit] = useState(50);
  const [testType, setTestType] = useState<string>("");
  const [targetMetric, setTargetMetric] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async () => {
    setBusy(true);
    setError(null);
    try {
      let parsedA: Record<string, unknown>;
      let parsedB: Record<string, unknown>;
      try {
        parsedA = variantA.trim() ? JSON.parse(variantA) : {};
        parsedB = variantB.trim() ? JSON.parse(variantB) : {};
      } catch {
        throw new Error("Variant A/B must be valid JSON");
      }
      await create({
        name, description: description || undefined, variant_a: parsedA, variant_b: parsedB, traffic_split: trafficSplit,
        test_type: testType || undefined, target_metric: targetMetric || undefined,
      });
      setName(""); setDescription(""); setVariantA(""); setVariantB(""); setTrafficSplit(50); setTestType(""); setTargetMetric("");
      onCreated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create the test");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-5">
      <h2 className="text-xs font-medium uppercase text-foreground-muted">New A/B test</h2>
      <input
        type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Test name"
        className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"
      />
      <input
        type="text" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description (optional)"
        className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ABTestVariantSelector label="Variant A (JSON)" value={variantA} onChange={setVariantA} placeholder='{"prompt": "..."}' />
        <ABTestVariantSelector label="Variant B (JSON)" value={variantB} onChange={setVariantB} placeholder='{"prompt": "..."}' />
      </div>
      <ABTestTrafficSplit value={trafficSplit} onChange={setTrafficSplit} />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <select value={testType} onChange={(e) => setTestType(e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
          <option value="">Test type (optional)</option>
          {TEST_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={targetMetric} onChange={(e) => setTargetMetric(e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
          <option value="">Target metric (optional)</option>
          {TARGET_METRICS.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
      <button
        type="button" disabled={busy || !name.trim()} onClick={() => void handleSubmit()}
        className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
      >
        Create test
      </button>
    </div>
  );
}
