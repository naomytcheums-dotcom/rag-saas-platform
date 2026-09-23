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
  name: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export const WORKFLOW_TEMPLATES: WorkflowTemplate[] = [
  {
    id: "simple-chatbot",
    name: "Chatbot simple",
    description: "Déclencheur → réponse LLM directe.",
    nodes: [
      { id: "trigger", type: "trigger", position: { x: 0, y: 0 } },
      { id: "llm", type: "llm_call", position: { x: 250, y: 0 }, data: { label: "Répondre", user_prompt: "{{ question }}" } },
    ],
    edges: [{ id: "e1", source: "trigger", target: "llm" }],
  },
  {
    id: "rag-pipeline",
    name: "Pipeline RAG",
    description: "Déclencheur → recherche dans la base de connaissances → réponse LLM.",
    nodes: [
      { id: "trigger", type: "trigger", position: { x: 0, y: 0 } },
      { id: "rag", type: "rag_search", position: { x: 250, y: 0 }, data: { label: "Rechercher", query: "{{ question }}" } },
      { id: "llm", type: "llm_call", position: { x: 500, y: 0 }, data: { label: "Répondre", user_prompt: "Contexte: {{ output }}\n\nQuestion: {{ question }}" } },
    ],
    edges: [
      { id: "e1", source: "trigger", target: "rag" },
      { id: "e2", source: "rag", target: "llm" },
    ],
  },
  {
    id: "approval-workflow",
    name: "Workflow avec approbation",
    description: "Déclencheur → génération LLM → approbation humaine avant envoi email.",
    nodes: [
      { id: "trigger", type: "trigger", position: { x: 0, y: 0 } },
      { id: "llm", type: "llm_call", position: { x: 250, y: 0 }, data: { label: "Générer", user_prompt: "{{ question }}" } },
      { id: "approve", type: "human", position: { x: 500, y: 0 }, data: { label: "Approuver ?", message: "Approuvez-vous l'envoi de cette réponse ?", input_type: "confirm" } },
      { id: "send", type: "email", position: { x: 750, y: 0 }, data: { label: "Envoyer", to: "", subject: "Réponse", body: "{{ output }}" } },
    ],
    edges: [
      { id: "e1", source: "trigger", target: "llm" },
      { id: "e2", source: "llm", target: "approve" },
      { id: "e3", source: "approve", target: "send" },
    ],
  },
];
