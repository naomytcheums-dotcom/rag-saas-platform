"use client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const SECTIONS = [
  { label: "Authentication", path: "#/auth" },
  { label: "Chat", path: "#/Public%20API/public_chat_endpoint" },
  { label: "Documents", path: "#/documents" },
  { label: "Agents", path: "#/agents" },
  { label: "API keys", path: "#/Public%20API" },
  { label: "Webhooks", path: "#/Webhooks" },
  { label: "Widget", path: "#/Widget" },
];

const SDK_LINKS = [
  { label: "Python SDK", href: "https://github.com/naomytcheums-dotcom/rag-saas-platform/tree/main/sdks/python" },
  { label: "JavaScript SDK", href: "https://github.com/naomytcheums-dotcom/rag-saas-platform/tree/main/sdks/js" },
  { label: "React SDK", href: "https://github.com/naomytcheums-dotcom/rag-saas-platform/tree/main/sdks/react" },
  { label: "Vue SDK", href: "https://github.com/naomytcheums-dotcom/rag-saas-platform/tree/main/sdks/vue" },
];

export default function ApiDocsPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-xl font-semibold text-foreground">API reference</h1>
      <p className="mt-1 text-sm text-foreground-muted">
        Real, honest scope: this links to FastAPI&apos;s own live, interactive Swagger UI (generated directly from
        the real code) rather than a second, hand-maintained copy that would inevitably drift out of sync. Opened in
        a new tab, not an iframe — <code>/docs</code> deliberately keeps the same real{" "}
        <code>X-Frame-Options: DENY</code> protection every other page on this API has.
      </p>

      <a
        href={`${API_BASE}/docs`}
        target="_blank"
        rel="noreferrer"
        className="mt-6 inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent-hover"
      >
        Open interactive API docs (Swagger UI) →
      </a>

      <div className="mt-8">
        <p className="text-xs font-semibold uppercase tracking-wide text-foreground-muted">Jump to a section</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {SECTIONS.map((section) => (
            <a
              key={section.label}
              href={`${API_BASE}/docs${section.path}`}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-border-strong px-3 py-1.5 text-sm text-foreground-muted transition-colors hover:border-accent hover:text-accent-hover"
            >
              {section.label}
            </a>
          ))}
        </div>
      </div>

      <div className="mt-8">
        <p className="text-xs font-semibold uppercase tracking-wide text-foreground-muted">SDKs</p>
        <div className="mt-2 flex flex-col gap-1.5">
          {SDK_LINKS.map((sdk) => (
            <a key={sdk.label} href={sdk.href} target="_blank" rel="noreferrer" className="text-sm text-accent hover:underline">
              {sdk.label}
            </a>
          ))}
        </div>
      </div>

      <a href={`${API_BASE}/openapi.json`} target="_blank" rel="noreferrer" className="mt-8 block text-xs text-foreground-muted hover:underline">
        Raw OpenAPI spec (JSON) →
      </a>
    </div>
  );
}
