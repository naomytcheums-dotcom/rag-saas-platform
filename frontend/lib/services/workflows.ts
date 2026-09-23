// Phase 5, Étape 5 -- workflow builder API client, api/routers/workflows.py's
// real surface (CRUD, run, run history, human-blocks, import/export,
// versions). Field names/shapes mirror the real backend schemas
// (api/schemas/workflows.py, workflow_triggers.py, workflow_human_input.py)
// exactly -- not invented client-side types.

import { api } from "@/lib/api";

// Same local re-declaration lib/useRealChat.ts already uses -- lib/api.ts
// deliberately doesn't export these (its own `request()` always sets
// the Authorization header itself); a real SSE GET needs the header
// set manually since the native EventSource API can't carry one at all.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("access_token");
}

export type WorkflowNodeType =
  | "trigger" | "llm_call" | "rag_search" | "web_search" | "http_call"
  | "condition" | "code" | "email" | "calendar" | "database" | "human";

export interface WorkflowNode {
  id: string;
  type: WorkflowNodeType;
  position: { x: number; y: number };
  data?: Record<string, unknown>;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
}

export interface Workflow {
  id: string;
  organization_id: string;
  workspace_id: string | null;
  name: string;
  description: string | null;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  variables: Record<string, unknown>[];
  status: string;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowValidateResponse {
  valid: boolean;
  errors: string[];
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  trigger_id: string | null;
  status: "pending" | "running" | "waiting_human" | "completed" | "failed";
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  error: string | null;
  context: Record<string, unknown> | null;
  current_node_id: string | null;
  started_at: string;
  completed_at: string | null;
}

export type HumanInputStatus = "pending" | "submitted" | "timeout";

export interface WorkflowHumanInput {
  id: string;
  workflow_run_id: string;
  node_id: string;
  message: string;
  input_type: string;
  options: unknown[] | null;
  required: boolean;
  status: HumanInputStatus;
  value: Record<string, unknown> | null;
  submitted_by: string | null;
  submitted_at: string | null;
  created_at: string;
  expires_at: string | null;
}

export interface WorkflowExport {
  name: string;
  description: string | null;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  variables: Record<string, unknown>[];
}

export const listWorkflows = (orgId: string, limit = 50, offset = 0) =>
  api.get<Workflow[]>(`/organizations/${orgId}/workflows?limit=${limit}&offset=${offset}`);

export const createWorkflow = (orgId: string, data: { name: string; description?: string; nodes?: WorkflowNode[]; edges?: WorkflowEdge[]; variables?: Record<string, unknown>[] }) =>
  api.post<Workflow>(`/organizations/${orgId}/workflows`, data);

export const getWorkflow = (id: string) => api.get<Workflow>(`/workflows/${id}`);

export const updateWorkflow = (id: string, data: Partial<{ name: string; description: string; nodes: WorkflowNode[]; edges: WorkflowEdge[]; variables: Record<string, unknown>[]; status: string }>) =>
  api.patch<Workflow>(`/workflows/${id}`, data);

export const deleteWorkflow = (id: string) => api.delete(`/workflows/${id}`);

export const validateWorkflow = (id: string) => api.post<WorkflowValidateResponse>(`/workflows/${id}/validate`);

export const runWorkflow = (id: string, input: Record<string, unknown> = {}) => api.post<WorkflowRun>(`/workflows/${id}/run`, { input });

export const listWorkflowRuns = (workflowId: string, limit = 50, offset = 0) =>
  api.get<WorkflowRun[]>(`/workflows/${workflowId}/runs?limit=${limit}&offset=${offset}`);

export const getWorkflowRun = (runId: string) => api.get<WorkflowRun>(`/workflows/runs/${runId}`);

export const listHumanBlocks = (runId: string) => api.get<WorkflowHumanInput[]>(`/workflows/runs/${runId}/human-blocks`);

export const submitHumanBlock = (runId: string, blockId: string, value: Record<string, unknown>) =>
  api.post<WorkflowHumanInput>(`/workflows/runs/${runId}/human-blocks/${blockId}/submit`, { value });

export const importWorkflow = (orgId: string, data: { name: string; description?: string; nodes: WorkflowNode[]; edges: WorkflowEdge[]; variables?: Record<string, unknown>[] }) =>
  api.post<Workflow>(`/organizations/${orgId}/workflows/import`, data);

export const exportWorkflow = (id: string) => api.get<WorkflowExport>(`/workflows/${id}/export`);

// Real `fetch` + stream reader, NOT the native EventSource -- same
// real reason lib/useRealChat.ts already documents: EventSource can't
// carry the Authorization header this backend requires
// (api/dependencies.get_current_user only reads it from that header,
// never a query param). Returns an abort function; `onEvent` is called
// once per real `data: {...}` frame (this backend's own SSE routes
// never set a named `event:` line, only `data:` -- see
// api/security/documents.py's own stream_document_progress for the
// identical wire format).
export function streamWorkflowRun(runId: string, onEvent: (event: Record<string, unknown>) => void, onDone?: () => void): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const token = getAccessToken();
      const response = await fetch(`${API_BASE_URL}/workflows/runs/${runId}/stream`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        credentials: "include",
        signal: controller.signal,
      });
      if (!response.ok || !response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let sepIndex: number;
        while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
          const rawEvent = buffer.slice(0, sepIndex);
          buffer = buffer.slice(sepIndex + 2);
          const dataLine = rawEvent.split("\n").find((line) => line.startsWith("data:"));
          if (!dataLine) continue;
          try {
            onEvent(JSON.parse(dataLine.slice(5).trim()));
          } catch {
            // a malformed frame is dropped, not fatal to the stream
          }
        }
      }
    } catch {
      // aborted or the connection dropped -- the caller decides whether to reconnect
    } finally {
      onDone?.();
    }
  })();

  return () => controller.abort();
}
