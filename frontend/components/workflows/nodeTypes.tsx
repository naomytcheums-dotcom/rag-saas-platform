"use client";

// Phase 5, Étape 5 -- one visual component per real backend block type
// (api/models/workflow.py's own BLOCK_TYPES, plus "trigger"). Kept
// deliberately simple (label + a one-line config summary) -- the real
// editing surface is NodeEditor.tsx's side panel, not inline node UI;
// React Flow's own convention (and every one of its official examples)
// keeps node components thin for exactly this reason.

import { Handle, Position, type NodeProps } from "reactflow";
import type { WorkflowNodeType } from "@/lib/services/workflows";

const NODE_META: Record<WorkflowNodeType, { label: string; color: string }> = {
  trigger: { label: "Déclencheur", color: "border-accent bg-accent-soft" },
  llm_call: { label: "LLM", color: "border-border-strong bg-surface" },
  rag_search: { label: "Recherche RAG", color: "border-border-strong bg-surface" },
  web_search: { label: "Recherche web", color: "border-border-strong bg-surface" },
  http_call: { label: "Appel HTTP", color: "border-border-strong bg-surface" },
  condition: { label: "Condition", color: "border-warning bg-warning-soft" },
  code: { label: "Code", color: "border-border-strong bg-surface" },
  email: { label: "Email", color: "border-border-strong bg-surface" },
  calendar: { label: "Calendrier", color: "border-border-strong bg-surface" },
  database: { label: "Base de données", color: "border-border-strong bg-surface" },
  human: { label: "Approbation humaine", color: "border-danger bg-danger-soft" },
};

function summarize(type: WorkflowNodeType, data: Record<string, unknown> | undefined): string {
  const d = data ?? {};
  switch (type) {
    case "llm_call":
      return typeof d.user_prompt === "string" ? d.user_prompt.slice(0, 40) : "(non configuré)";
    case "rag_search":
    case "web_search":
    case "database":
      return typeof d.query === "string" ? d.query.slice(0, 40) : "(non configuré)";
    case "http_call":
      return typeof d.url === "string" ? d.url.slice(0, 40) : "(non configuré)";
    case "condition":
      return typeof d.condition === "string" ? d.condition.slice(0, 40) : "(non configuré)";
    case "code":
      return typeof d.language === "string" ? d.language : "python";
    case "email":
      return typeof d.subject === "string" ? d.subject.slice(0, 40) : "(non configuré)";
    case "human":
      return typeof d.message === "string" ? d.message.slice(0, 40) : "(non configuré)";
    default:
      return "";
  }
}

function BaseNode({ id, type, data, selected }: NodeProps) {
  const nodeType = type as WorkflowNodeType;
  const meta = NODE_META[nodeType] ?? { label: type, color: "border-border bg-surface" };
  const isCondition = nodeType === "condition";
  const isTrigger = nodeType === "trigger";

  return (
    <div
      data-testid={`workflow-node-${id}`}
      className={`min-w-[160px] rounded-lg border-2 px-3 py-2 shadow-sm ${meta.color} ${selected ? "ring-2 ring-accent" : ""}`}
    >
      {!isTrigger && <Handle type="target" position={Position.Left} />}
      <p className="text-xs font-semibold text-foreground">{(data?.label as string) || meta.label}</p>
      <p className="mt-0.5 truncate text-[11px] text-foreground-muted">{summarize(nodeType, data)}</p>
      {isCondition ? (
        <div className="mt-1 flex justify-between text-[10px] text-foreground-muted">
          <span>Vrai</span>
          <span>Faux</span>
        </div>
      ) : null}
      {isCondition ? (
        <>
          <Handle type="source" position={Position.Right} id="true" style={{ top: "35%" }} />
          <Handle type="source" position={Position.Right} id="false" style={{ top: "65%" }} />
        </>
      ) : nodeType !== "human" ? (
        <Handle type="source" position={Position.Right} />
      ) : (
        <Handle type="source" position={Position.Right} />
      )}
    </div>
  );
}

export const nodeTypes = {
  trigger: BaseNode,
  llm_call: BaseNode,
  rag_search: BaseNode,
  web_search: BaseNode,
  http_call: BaseNode,
  condition: BaseNode,
  code: BaseNode,
  email: BaseNode,
  calendar: BaseNode,
  database: BaseNode,
  human: BaseNode,
};

export const NODE_TYPE_OPTIONS: { value: WorkflowNodeType; label: string }[] = (
  Object.keys(NODE_META) as WorkflowNodeType[]
).map((value) => ({ value, label: NODE_META[value].label }));

export { NODE_META };
