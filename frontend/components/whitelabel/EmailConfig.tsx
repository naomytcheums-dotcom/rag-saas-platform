"use client";

import { useState } from "react";

interface EmailConfigProps {
  senderName: string | null;
  senderEmail: string | null;
  onConfigure: (data: { sender_name: string; sender_email: string }) => Promise<unknown>;
  onRemove: () => Promise<unknown>;
}

export function EmailConfig({ senderName, senderEmail, onConfigure, onRemove }: EmailConfigProps) {
  const [name, setName] = useState(senderName ?? "");
  const [email, setEmail] = useState(senderEmail ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setBusy(true);
    setError(null);
    try {
      await onConfigure({ sender_name: name, sender_email: email });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the email sender identity");
    } finally {
      setBusy(false);
    }
  };

  const handleRemove = async () => {
    setBusy(true);
    try {
      await onRemove();
      setName("");
      setEmail("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h2 className="text-xs font-medium uppercase text-foreground-muted">Email sender identity</h2>
      <p className="mt-1 text-xs text-foreground-muted">The reply-to name/address shown on outbound emails from your organization.</p>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <input
          type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Sender name"
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"
        />
        <input
          type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="sender@yourdomain.com"
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"
        />
      </div>
      <div className="mt-3 flex gap-2">
        <button
          type="button" disabled={busy || !name.trim() || !email.trim()} onClick={() => void handleSave()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          Save
        </button>
        {(senderName || senderEmail) && (
          <button type="button" disabled={busy} onClick={() => void handleRemove()} className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground-muted hover:text-danger">
            Remove
          </button>
        )}
      </div>
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
    </div>
  );
}
