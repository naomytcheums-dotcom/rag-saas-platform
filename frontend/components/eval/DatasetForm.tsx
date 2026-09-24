"use client";

import { useState } from "react";
import * as evalService from "@/lib/services/eval";

export function DatasetForm({ orgId, onCreated }: { orgId: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await evalService.createDataset(orgId, { name: name.trim(), description: description.trim() || undefined });
      setName("");
      setDescription("");
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create dataset");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      {error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      <input
        value={name} onChange={(e) => setName(e.target.value)} placeholder="Dataset name" required
        className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
      />
      <textarea
        value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description (optional)" rows={2}
        className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
      />
      <button type="submit" disabled={submitting || !name.trim()} className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {submitting ? "Creating…" : "Create dataset"}
      </button>
    </form>
  );
}
