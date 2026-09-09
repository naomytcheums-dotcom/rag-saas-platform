import type { RagSaasClient } from "../client.js";
import type { ChatResponse } from "../types.js";

export class ChatEndpoint {
  constructor(private readonly client: RagSaasClient) {}

  /** Literal ask: `chat.send(message, agentId, conversationId)`. */
  send(message: string, agentId: string, conversationId?: string): Promise<ChatResponse> {
    return this.client.request<ChatResponse>("POST", "/v1/chat", {
      json: { message, agent_id: agentId, conversation_id: conversationId ?? null, stream: false },
    });
  }
}
