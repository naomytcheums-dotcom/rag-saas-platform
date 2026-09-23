// Mirrors api/models/workflow.py's own real BLOCK_TYPES + "trigger"
// exactly -- kept as its own small module (not inside workflows.ts)
// so validator.ts can import just the constant without pulling in the
// full API client (and its own `api`/fetch dependency) into a pure,
// synchronous validation function that vitest can unit-test in isolation.

import type { WorkflowNodeType } from "@/lib/services/workflows";

export const BLOCK_TYPES: WorkflowNodeType[] = [
  "trigger", "llm_call", "rag_search", "web_search", "http_call", "condition", "code", "human", "email", "calendar", "database",
];
