import type { RagSaasClient } from "../client.js";
import type { AnalyticsResponse } from "../types.js";

export class AnalyticsEndpoint {
  constructor(private readonly client: RagSaasClient) {}

  /** Literal ask: `analytics.get(period, metrics)`. */
  get(period = "month", metrics?: string[]): Promise<AnalyticsResponse> {
    return this.client.request<AnalyticsResponse>("GET", "/v1/analytics", {
      params: { period, metrics: metrics?.join(",") },
    });
  }
}
