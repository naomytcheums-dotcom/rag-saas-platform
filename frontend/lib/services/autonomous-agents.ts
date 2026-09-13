// Partie 23 -- autonomous agents API client, api/routers/autonomous_agents.py's
// real surface.

import { api } from "@/lib/api";

export type AutonomousAgentStatus = "idle" | "planning" | "executing" | "paused" | "completed" | "error";

export interface AutonomousAgent {
  id: string;
  organization_id: string;
  created_by: string | null;
  name: string;
  description: string | null;
  goal: string;
  status: AutonomousAgentStatus;
  max_steps: number;
  current_step: number;
  tools_enabled: { name: string; enabled: boolean; config?: Record<string, unknown> }[];
  guardrails: Record<string, unknown>;
  memory_config: Record<string, unknown>;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface AutonomousAgentListResponse {
  items: AutonomousAgent[];
  total: number;
  limit: number;
  offset: number;
}

export interface AgentStatus {
  status: AutonomousAgentStatus;
  current_step: number;
  max_steps: number;
  error: string | null;
}

export interface AgentPlan {
  id: string;
  agent_id: string;
  goal: string;
  steps: { description: string; depends_on: number[] }[];
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
}

export interface AgentStep {
  id: string;
  plan_id: string;
  step_number: number;
  action: string;
  parameters: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface AgentMemory {
  id: string;
  agent_id: string;
  memory_type: "short_term" | "long_term" | "episodic";
  content: string;
  importance: number;
  created_at: string;
}

export interface AgentCollaboration {
  id: string;
  initiator_agent_id: string;
  collaborator_agent_id: string;
  task: string;
  status: "pending" | "accepted" | "running" | "completed" | "failed";
  result: Record<string, unknown> | null;
  created_at: string;
}

export const listAutonomousAgents = (orgId: string, limit = 50, offset = 0) =>
  api.get<AutonomousAgentListResponse>(`/organizations/${orgId}/autonomous-agents?limit=${limit}&offset=${offset}`);

export const createAutonomousAgent = (orgId: string, data: {
  name: string; description?: string; goal: string; max_steps?: number;
  tools_enabled?: Record<string, unknown>[]; guardrails?: Record<string, unknown>; memory_config?: Record<string, unknown>;
}) => api.post<AutonomousAgent>(`/organizations/${orgId}/autonomous-agents`, data);

export const getAutonomousAgent = (id: string) => api.get<AutonomousAgent>(`/autonomous-agents/${id}`);

export const updateAutonomousAgent = (id: string, data: Partial<Pick<AutonomousAgent, "name" | "description" | "goal" | "max_steps" | "tools_enabled" | "guardrails" | "memory_config">>) =>
  api.patch<AutonomousAgent>(`/autonomous-agents/${id}`, data);

export const deleteAutonomousAgent = (id: string) => api.delete(`/autonomous-agents/${id}`);

export const runAutonomousAgent = (id: string) => api.post<AutonomousAgent>(`/autonomous-agents/${id}/run`);
export const pauseAutonomousAgent = (id: string) => api.post<AutonomousAgent>(`/autonomous-agents/${id}/pause`);
export const resumeAutonomousAgent = (id: string) => api.post<AutonomousAgent>(`/autonomous-agents/${id}/resume`);
export const stopAutonomousAgent = (id: string) => api.post<AutonomousAgent>(`/autonomous-agents/${id}/stop`);
export const getAgentStatus = (id: string) => api.get<AgentStatus>(`/autonomous-agents/${id}/status`);

export const listAgentPlans = (id: string) => api.get<AgentPlan[]>(`/autonomous-agents/${id}/plans`);
export const getAgentPlan = (id: string, planId: string) => api.get<AgentPlan>(`/autonomous-agents/${id}/plans/${planId}`);
export const listAgentSteps = (id: string, planId: string) => api.get<AgentStep[]>(`/autonomous-agents/${id}/plans/${planId}/steps`);

export const getAgentMemory = (id: string, memoryType?: string) =>
  api.get<AgentMemory[]>(`/autonomous-agents/${id}/memory${memoryType ? `?memory_type=${memoryType}` : ""}`);
export const addAgentMemory = (id: string, data: { content: string; memory_type?: string; importance?: number }) =>
  api.post<AgentMemory>(`/autonomous-agents/${id}/memory`, data);
export const deleteAgentMemory = (id: string, memoryId: string) => api.delete(`/autonomous-agents/${id}/memory/${memoryId}`);

export const collaborateAgents = (id: string, data: { collaborator_agent_id: string; task: string }) =>
  api.post<AgentCollaboration>(`/autonomous-agents/${id}/collaborate`, data);
export const listCollaborations = (id: string) => api.get<AgentCollaboration[]>(`/autonomous-agents/${id}/collaborations`);
