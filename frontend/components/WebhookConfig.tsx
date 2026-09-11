"use client";

interface WebhookConfigProps {
  connectionId: string;
  provider: string;
  token?: string; // only present right after creation -- never re-fetchable
}

const PROVIDER_HINT: Record<string, string> = {
  webhook: "Any system that can POST JSON with a bearer token.",
  zapier: "Use a 'Webhooks by Zapier' action pointed at this URL.",
  make: "Use an HTTP module pointed at this URL.",
  n8n: "Use an HTTP Request node pointed at this URL.",
};

// Partie 15.1 -- the real inbound receiver URL for one connection
// (POST /integrations/inbound/{connection_id}, api/routers/
// integrations_universal.py). The token is shown once, at creation
// only, the same real convention as an API key's own plaintext.
export default function WebhookConfig({ connectionId, provider, token }: WebhookConfigProps) {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const url = `${base}/integrations/inbound/${connectionId}`;

  return (
    <div className="rounded-lg border border-border bg-background p-3 text-xs">
      <p className="text-foreground-muted">{PROVIDER_HINT[provider] ?? PROVIDER_HINT.webhook}</p>
      <p className="mt-2 break-all font-mono text-foreground">{url}</p>
      {token ? (
        <>
          <p className="mt-1 break-all font-mono text-foreground">Authorization: Bearer {token}</p>
          <p className="mt-2 font-medium text-danger">Save this token now — it won&apos;t be shown again.</p>
        </>
      ) : (
        <p className="mt-2 text-foreground-muted">The bearer token was shown once, at creation. Delete and recreate this connection to get a new one.</p>
      )}
    </div>
  );
}
