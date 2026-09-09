import type { RagSaasClient } from "../client.js";
import type { EmbedResponse } from "../types.js";

export class EmbedEndpoint {
  constructor(private readonly client: RagSaasClient) {}

  /** Literal ask: `embed.generate(text, model)`. */
  generate(text: string, model?: string): Promise<EmbedResponse> {
    return this.client.request<EmbedResponse>("POST", "/v1/embed", {
      json: { text, model: model ?? null },
    });
  }
}
