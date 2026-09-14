"use client";

import { ModelCard } from "@/components/fine-tuning/ModelCard";
import { useFineTunedModels } from "@/lib/hooks/useFineTunedModels";

export function ModelList({ orgId }: { orgId: string }) {
  const { models, loading, error, deploy, undeploy, remove } = useFineTunedModels(orgId);

  if (loading) return <p className="text-sm text-foreground-muted">Loading…</p>;
  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (models.length === 0) return <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No fine-tuned models yet.</p>;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {models.map((model) => <ModelCard key={model.id} model={model} onDeploy={deploy} onUndeploy={undeploy} onDelete={remove} />)}
    </div>
  );
}
