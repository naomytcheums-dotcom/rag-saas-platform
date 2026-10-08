import type { RagSaasClient } from "../client.js";
import type { KnowledgeBaseCreateResponse, ListOptions } from "../types.js";

export class KnowledgeBasesEndpoint {
  constructor(private readonly client: RagSaasClient) {}

  /** `GET /v1/knowledge-bases` (scope `kb:read`). */
  list(options: ListOptions = {}): Promise<Record<string, unknown>[]> {
    return this.client.request<Record<string, unknown>[]>("GET", "/v1/knowledge-bases", {
      params: { limit: String(options.limit ?? 20), offset: String(options.offset ?? 0) },
    });
  }

  /** `POST /v1/knowledge-bases` (scope `kb:write`). */
  create(name: string, description?: string, config?: Record<string, unknown>): Promise<KnowledgeBaseCreateResponse> {
    return this.client.request<KnowledgeBaseCreateResponse>("POST", "/v1/knowledge-bases", {
      json: { name, description: description ?? null, config: config ?? null },
    });
  }
}
