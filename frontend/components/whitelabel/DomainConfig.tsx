"use client";

import { useState } from "react";

interface DomainConfigProps {
  domain: string | null;
  domainVerified: boolean;
  onSet: (domain: string) => Promise<unknown>;
  onRemove: () => Promise<unknown>;
  onVerify: () => Promise<unknown>;
}

export function DomainConfig({ domain, domainVerified, onSet, onRemove, onVerify }: DomainConfigProps) {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSet = async () => {
    setBusy(true);
    setError(null);
    try {
      await onSet(input.trim());
      setInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not set this domain");
    } finally {
      setBusy(false);
    }
  };

  const handleVerify = async () => {
    setBusy(true);
    try {
      await onVerify();
    } finally {
      setBusy(false);
    }
  };

  const handleRemove = async () => {
    setBusy(true);
    try {
      await onRemove();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h2 className="text-xs font-medium uppercase text-foreground-muted">Custom domain</h2>
      {domain ? (
        <div className="mt-3 flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-foreground">{domain}</span>
            <span className={domainVerified ? "rounded-full bg-success-soft px-2 py-0.5 text-xs text-success" : "rounded-full bg-surface-muted px-2 py-0.5 text-xs text-foreground-muted"}>
              {domainVerified ? "Verified" : "Pending verification"}
            </span>
          </div>
          {!domainVerified && (
            <p className="text-xs text-foreground-muted">
              Add a CNAME record pointing this domain at this platform&apos;s own domain, then verify. DNS propagation can take up to a few hours.
            </p>
          )}
          <div className="flex gap-2">
            {!domainVerified && (
              <button type="button" disabled={busy} onClick={() => void handleVerify()} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50">
                Verify now
              </button>
            )}
            <button type="button" disabled={busy} onClick={() => void handleRemove()} className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground-muted hover:text-danger">
              Remove
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex gap-2">
          <input
            type="text" value={input} onChange={(e) => setInput(e.target.value)} placeholder="app.your-domain.com"
            className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"
          />
          <button
            type="button" disabled={busy || !input.trim()} onClick={() => void handleSet()}
            className="shrink-0 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            Add
          </button>
        </div>
      )}
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
    </div>
  );
}
