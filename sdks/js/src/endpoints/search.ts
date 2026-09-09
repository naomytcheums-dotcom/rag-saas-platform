import type { RagSaasClient } from "../client.js";
import type { SearchResponse } from "../types.js";

export class SearchEndpoint {
  constructor(private readonly client: RagSaasClient) {}

  /** Literal ask: `search.query(query, workspaceId, filters, topK)`. */
  query(query: string, workspaceId?: string, filters?: Record<string, unknown>, topK = 5): Promise<SearchResponse> {
    return this.client.request<SearchResponse>("POST", "/v1/search", {
      json: { query, workspace_id: workspaceId ?? null, filters: filters ?? null, top_k: topK },
    });
  }
}
