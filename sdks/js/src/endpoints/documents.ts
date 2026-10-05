import type { RagSaasClient } from "../client.js";
import type { DocumentUploadResponse, ListOptions } from "../types.js";

export class DocumentsEndpoint {
  constructor(private readonly client: RagSaasClient) {}

  /** Literal ask: `documents.upload(file, workspaceId)`.
   * `file` accepts a `Blob`/`File` (browser) or a `Buffer` with a `filename` (Node). */
  upload(file: Blob | { data: Buffer; filename: string }, workspaceId?: string): Promise<DocumentUploadResponse> {
    const form = new FormData();
    if (file instanceof Blob) {
      form.set("file", file);
    } else {
      form.set("file", new Blob([new Uint8Array(file.data)]), file.filename);
    }
    return this.client.request<DocumentUploadResponse>("POST", "/v1/documents", {
      body: form,
      params: { workspace_id: workspaceId },
    });
  }

  /** `GET /v1/documents` (scope `documents:read`). */
  list(options: ListOptions = {}): Promise<Record<string, unknown>[]> {
    return this.client.request<Record<string, unknown>[]>("GET", "/v1/documents", {
      params: { limit: String(options.limit ?? 20), offset: String(options.offset ?? 0) },
    });
  }
}
