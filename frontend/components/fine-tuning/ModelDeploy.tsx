"use client";

import type { FineTunedModel } from "@/lib/services/fine-tuning";

interface ModelDeployProps {
  model: FineTunedModel;
  onDeploy: (id: string) => void | Promise<void>;
  onUndeploy: (id: string) => void | Promise<void>;
}

export function ModelDeploy({ model, onDeploy, onUndeploy }: ModelDeployProps) {
  if (model.status === "deprecated") {
    return <span className="text-xs text-foreground-muted">Deprecated — cannot be deployed</span>;
  }
  return model.deployed ? (
    <button type="button" onClick={() => void onUndeploy(model.id)} className="rounded-lg border border-border px-3 py-1 text-xs font-medium text-foreground hover:bg-surface-muted">
      Undeploy
    </button>
  ) : (
    <button type="button" onClick={() => void onDeploy(model.id)} className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent-hover">
      Deploy
    </button>
  );
}
