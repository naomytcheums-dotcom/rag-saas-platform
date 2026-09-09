import type { RagSaasClient } from "../client.js";
import type { UsageResponse } from "../types.js";

export class UsageEndpoint {
  constructor(private readonly client: RagSaasClient) {}

  /** Literal ask: `usage.get(period, metric)`. */
  get(period = "month", metric?: string): Promise<UsageResponse> {
    return this.client.request<UsageResponse>("GET", "/v1/usage", {
      params: { period, metric },
    });
  }
}
