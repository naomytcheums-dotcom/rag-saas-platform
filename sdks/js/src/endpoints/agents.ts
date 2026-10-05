import type { RagSaasClient } from "../client.js";
import type { AgentRunResponse, ListOptions } from "../types.js";

export class AgentsEndpoint {
  constructor(private readonly client: RagSaasClient) {}

  /** Literal ask: `agents.run(agentId, input, conversationId)`. */
  run(agentId: string, input: string, conversationId?: string): Promise<AgentRunResponse> {
    return this.client.request<AgentRunResponse>("POST", "/v1/agents/run", {
      json: { agent_id: agentId, input, conversation_id: conversationId ?? null },
    });
  }

  /** `GET /v1/agents` (scope `agents:read`). */
  list(options: ListOptions = {}): Promise<Record<string, unknown>[]> {
    return this.client.request<Record<string, unknown>[]>("GET", "/v1/agents", {
      params: { limit: String(options.limit ?? 20), offset: String(options.offset ?? 0) },
    });
  }
}
