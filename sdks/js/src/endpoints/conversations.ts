import type { RagSaasClient } from "../client.js";
import type { ConversationListResponse, ListOptions } from "../types.js";

export class ConversationsEndpoint {
  constructor(private readonly client: RagSaasClient) {}

  /** `GET /v1/conversations` (scope `chat:read`). */
  list(options: ListOptions & { agentId?: string } = {}): Promise<ConversationListResponse> {
    return this.client.request<ConversationListResponse>("GET", "/v1/conversations", {
      params: { limit: String(options.limit ?? 20), offset: String(options.offset ?? 0), agent_id: options.agentId },
    });
  }
}
