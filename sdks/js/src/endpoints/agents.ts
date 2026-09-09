import type { RagSaasClient } from "../client.js";
import type { AgentRunResponse } from "../types.js";

export class AgentsEndpoint {
  constructor(private readonly client: RagSaasClient) {}

  /** Literal ask: `agents.run(agentId, input, conversationId)`. */
  run(agentId: string, input: string, conversationId?: string): Promise<AgentRunResponse> {
    return this.client.request<AgentRunResponse>("POST", "/v1/agents/run", {
      json: { agent_id: agentId, input, conversation_id: conversationId ?? null },
    });
  }
}
