// Phase 5, Étape 5 -- client-side validation mirroring
// api/services/workflows.py's own real `validate_workflow` EXACTLY
// (duplicate ids, unknown node type, dangling edge references) so a
// user sees the same errors instantly, before ever hitting
// POST /workflows/{id}/validate. Real, deliberate deviation from the
// étape's own literal "no cycles" rule: the backend executor doesn't
// reject a cyclic graph outright either (api/services/workflow_engine.py's
// own MAX_STEPS cap bounds it at runtime instead) -- a strict client-side
// cycle rejection would block graphs the backend actually accepts, so
// a cycle is surfaced as a WARNING here, not a blocking error.

import { BLOCK_TYPES } from "@/lib/services/workflowConstants";
import type { WorkflowEdge, WorkflowNode } from "@/lib/services/workflows";

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

function hasCycle(nodes: WorkflowNode[], edges: WorkflowEdge[]): boolean {
  const adjacency = new Map<string, string[]>();
  for (const edge of edges) {
    adjacency.set(edge.source, [...(adjacency.get(edge.source) ?? []), edge.target]);
  }
  const WHITE = 0, GRAY = 1, BLACK = 2;
  const color = new Map<string, number>(nodes.map((n) => [n.id, WHITE]));

  function visit(nodeId: string): boolean {
    color.set(nodeId, GRAY);
    for (const next of adjacency.get(nodeId) ?? []) {
      const state = color.get(next);
      if (state === GRAY) return true;
      if (state === WHITE && visit(next)) return true;
    }
    color.set(nodeId, BLACK);
    return false;
  }

  return nodes.some((n) => color.get(n.id) === WHITE && visit(n.id));
}

export function validateWorkflow(nodes: WorkflowNode[], edges: WorkflowEdge[]): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  const ids = nodes.map((n) => n.id);
  if (new Set(ids).size !== ids.length) errors.push("Des identifiants de nœuds sont dupliqués");

  for (const node of nodes) {
    if (!BLOCK_TYPES.includes(node.type)) errors.push(`Le nœud '${node.id}' a un type inconnu : '${node.type}'`);
  }

  const realIds = new Set(ids);
  for (const edge of edges) {
    if (!realIds.has(edge.source) || !realIds.has(edge.target)) errors.push(`La connexion '${edge.id}' référence un nœud inconnu`);
  }

  if (nodes.length > 0 && hasCycle(nodes, edges)) warnings.push("Ce workflow contient un cycle -- l'exécution s'arrêtera après un nombre maximal d'étapes plutôt que de boucler indéfiniment");

  const orphanIds = nodes.filter((n) => n.type !== "trigger" && !edges.some((e) => e.target === n.id)).map((n) => n.id);
  if (orphanIds.length > 0) warnings.push(`Nœud(s) inaccessibles depuis le déclencheur : ${orphanIds.join(", ")}`);

  return { valid: errors.length === 0, errors, warnings };
}
