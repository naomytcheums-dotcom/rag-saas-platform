// Phase 5, Étape 5 -- code-defined starter templates (decision:
// client-side, not a DB-backed template CRUD -- see this étape's own
// final report section C for why: `Workflow` is already a real,
// working, DB-backed CRUD entity; "use a template" is just "create a
// workflow pre-filled with these nodes/edges", exactly the same
// "don't add a second, competing source of truth" reasoning this
// codebase already applied to billing Plans (Phase 5, Étape 2) and
// notification templates (Phase 5, Étape 4).

import type { WorkflowEdge, WorkflowNode } from "@/lib/services/workflows";

export interface WorkflowTemplate {
  id: string;
  /** i18n key, resolved with t() by the consumer */
  nameKey: string;
  /** i18n key, resolved with t() by the consumer */
  descriptionKey: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export const WORKFLOW_TEMPLATES: WorkflowTemplate[] = [
  {
    id: "simple-chatbot",
    nameKey: "workflow_tpl.chatbot_name",
    descriptionKey: "workflow_tpl.chatbot_desc",
    nodes: [
      { id: "trigger", type: "trigger", position: { x: 0, y: 0 } },
      { id: "llm", type: "llm_call", position: { x: 250, y: 0 }, data: { labelKey: "workflow_tpl.chatbot_node_respond", user_prompt: "{{ question }}" } },
    ],
    edges: [{ id: "e1", source: "trigger", target: "llm" }],
  },
  {
    id: "rag-pipeline",
    nameKey: "workflow_tpl.rag_name",
    descriptionKey: "workflow_tpl.rag_desc",
    nodes: [
      { id: "trigger", type: "trigger", position: { x: 0, y: 0 } },
      { id: "rag", type: "rag_search", position: { x: 250, y: 0 }, data: { labelKey: "workflow_tpl.rag_node_search", query: "{{ question }}" } },
      { id: "llm", type: "llm_call", position: { x: 500, y: 0 }, data: { labelKey: "workflow_tpl.chatbot_node_respond", user_prompt: "Contexte: {{ output }}\n\nQuestion: {{ question }}" } },
    ],
    edges: [
      { id: "e1", source: "trigger", target: "rag" },
      { id: "e2", source: "rag", target: "llm" },
    ],
  },
  {
    id: "approval-workflow",
    nameKey: "workflow_tpl.approval_name",
    descriptionKey: "workflow_tpl.approval_desc",
    nodes: [
      { id: "trigger", type: "trigger", position: { x: 0, y: 0 } },
      { id: "llm", type: "llm_call", position: { x: 250, y: 0 }, data: { labelKey: "workflow_tpl.approval_node_generate", user_prompt: "{{ question }}" } },
      { id: "approve", type: "human", position: { x: 500, y: 0 }, data: { labelKey: "workflow_tpl.approval_node_approve", messageKey: "workflow_tpl.approval_node_approve_msg", input_type: "confirm" } },
      { id: "send", type: "email", position: { x: 750, y: 0 }, data: { labelKey: "workflow_tpl.approval_node_send", to: "", subjectKey: "workflow_tpl.approval_email_subject", body: "{{ output }}" } },
    ],
    edges: [
      { id: "e1", source: "trigger", target: "llm" },
      { id: "e2", source: "llm", target: "approve" },
      { id: "e3", source: "approve", target: "send" },
    ],
  },
];
