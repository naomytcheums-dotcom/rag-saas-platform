"use client";

import { useState } from "react";
import { ModelDeploy } from "@/components/fine-tuning/ModelDeploy";
import { ModelEvaluation } from "@/components/fine-tuning/ModelEvaluation";
import type { FineTunedModel } from "@/lib/services/fine-tuning";

interface ModelCardProps {
  model: FineTunedModel;
  onDeploy: (id: string) => void | Promise<void>;
  onUndeploy: (id: string) => void | Promise<void>;
  onDelete: (id: string) => void | Promise<void>;
}

export function ModelCard({ model, onDeploy, onUndeploy, onDelete }: ModelCardProps) {
  const [showEval, setShowEval] = useState(false);

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{model.name}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${model.status === "available" ? "bg-success-soft text-success" : "bg-surface-muted text-foreground-muted"}`}>
          {model.status}
        </span>
      </div>
      <div className="mt-2 flex gap-3 text-xs text-foreground-muted">
        <span>{model.provider}</span>
        <span>{model.base_model}</span>
        {model.deployed && <span className="text-accent">Deployed</span>}
      </div>

      <div className="mt-3 flex gap-2">
        <ModelDeploy model={model} onDeploy={onDeploy} onUndeploy={onUndeploy} />
        <button type="button" onClick={() => setShowEval((s) => !s)} className="rounded-lg border border-border px-3 py-1 text-xs font-medium text-foreground hover:bg-surface-muted">
          {showEval ? "Hide evaluation" : "Evaluate"}
        </button>
        <button type="button" onClick={() => void onDelete(model.id)} className="rounded-lg border border-danger px-3 py-1 text-xs font-medium text-danger hover:bg-danger-soft">
          Delete
        </button>
      </div>

      {showEval && <div className="mt-3"><ModelEvaluation modelId={model.id} /></div>}
    </div>
  );
}
