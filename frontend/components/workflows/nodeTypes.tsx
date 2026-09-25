"use client";

// Phase 5, Étape 5 -- one visual component per real backend block type
// (api/models/workflow.py's own BLOCK_TYPES, plus "trigger"). Kept
// deliberately simple (label + a one-line config summary) -- the real
// editing surface is NodeEditor.tsx's side panel, not inline node UI;
// React Flow's own convention (and every one of its official examples)
// keeps node components thin for exactly this reason.

import { Handle, Position, type NodeProps } from "reactflow";
import type { WorkflowNodeType } from "@/lib/services/workflows";
import { useTranslation } from "@/lib/i18n";

const NODE_META: Record<WorkflowNodeType, { labelKey: string; color: string }> = {
  trigger: { labelKey: "workflow_node.trigger", color: "border-accent bg-accent-soft" },
  llm_call: { labelKey: "workflow_node.llm_call", color: "border-border-strong bg-surface" },
  rag_search: { labelKey: "workflow_node.rag_search", color: "border-border-strong bg-surface" },
  web_search: { labelKey: "workflow_node.web_search", color: "border-border-strong bg-surface" },
  http_call: { labelKey: "workflow_node.http_call", color: "border-border-strong bg-surface" },
  condition: { labelKey: "workflow_node.condition", color: "border-warning bg-warning-soft" },
  code: { labelKey: "workflow_node.code", color: "border-border-strong bg-surface" },
  email: { labelKey: "workflow_node.email", color: "border-border-strong bg-surface" },
  calendar: { labelKey: "workflow_node.calendar", color: "border-border-strong bg-surface" },
  database: { labelKey: "workflow_node.database", color: "border-border-strong bg-surface" },
  human: { labelKey: "workflow_node.human", color: "border-danger bg-danger-soft" },
};

function summarize(type: WorkflowNodeType, data: Record<string, unknown> | undefined, t: (key: string) => string): string {
  const d = data ?? {};
  switch (type) {
    case "llm_call":
      return typeof d.user_prompt === "string" ? d.user_prompt.slice(0, 40) : t("workflow_node.not_configured");
    case "rag_search":
    case "web_search":
    case "database":
      return typeof d.query === "string" ? d.query.slice(0, 40) : t("workflow_node.not_configured");
    case "http_call":
      return typeof d.url === "string" ? d.url.slice(0, 40) : t("workflow_node.not_configured");
    case "condition":
      return typeof d.condition === "string" ? d.condition.slice(0, 40) : t("workflow_node.not_configured");
    case "code":
      return typeof d.language === "string" ? d.language : "python";
    case "email":
      return typeof d.subject === "string" ? d.subject.slice(0, 40) : t("workflow_node.not_configured");
    case "human":
      return typeof d.message === "string" ? d.message.slice(0, 40) : t("workflow_node.not_configured");
    default:
      return "";
  }
}

function BaseNode({ id, type, data, selected }: NodeProps) {
  const { t } = useTranslation();
  const nodeType = type as WorkflowNodeType;
  const meta = NODE_META[nodeType] ?? { labelKey: type, color: "border-border bg-surface" };
  const isCondition = nodeType === "condition";
  const isTrigger = nodeType === "trigger";

  return (
    <div
      data-testid={`workflow-node-${id}`}
      className={`min-w-[160px] rounded-lg border-2 px-3 py-2 shadow-sm ${meta.color} ${selected ? "ring-2 ring-accent" : ""}`}
    >
      {!isTrigger && <Handle type="target" position={Position.Left} />}
      <p className="text-xs font-semibold text-foreground">{(data?.label as string) || t(meta.labelKey)}</p>
      <p className="mt-0.5 truncate text-[11px] text-foreground-muted">{summarize(nodeType, data, t)}</p>
      {isCondition ? (
        <div className="mt-1 flex justify-between text-[10px] text-foreground-muted">
          <span>{t("workflow_node.true")}</span>
          <span>{t("workflow_node.false")}</span>
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

export const NODE_TYPE_OPTIONS: { value: WorkflowNodeType; labelKey: string }[] = (
  Object.keys(NODE_META) as WorkflowNodeType[]
).map((value) => ({ value, labelKey: NODE_META[value].labelKey }));

export { NODE_META };
