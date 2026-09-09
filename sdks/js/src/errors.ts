export class RagSaasAPIError extends Error {
  readonly statusCode: number;
  readonly detail: unknown;

  constructor(statusCode: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `RAG SaaS API error (status ${statusCode})`);
    this.name = "RagSaasAPIError";
    this.statusCode = statusCode;
    this.detail = detail;
  }
}
