"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { createPlugin, listPluginPermissions } from "@/lib/services/plugins";
import type { Plugin, PluginPermission } from "@/lib/types";

interface PluginCreateFormProps {
  orgId: string;
  onPublished?: (plugin: Plugin) => void;
  onError?: (message: string) => void;
}

const CATEGORIES = ["analytics", "automation", "communication", "data", "integration", "productivity", "security", "other"];

// Partie 16 (ter) -- POST /organizations/{org_id}/plugins/publish.
// Publishing always creates a new `pending` plugin, reviewed by an
// admin before it appears in the marketplace.
export default function PluginCreateForm({ orgId, onPublished, onError }: PluginCreateFormProps) {
  const [permissions, setPermissions] = useState<PluginPermission[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("other");
  const [pricing, setPricing] = useState("free");
  const [price, setPrice] = useState("");
  const [version, setVersion] = useState("1.0.0");
  const [entryPoint, setEntryPoint] = useState("index.js");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [codeText, setCodeText] = useState("// your plugin code here\n");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void listPluginPermissions().then(setPermissions).catch(() => setPermissions([]));
  }, []);

  function togglePermission(id: string) {
    setSelectedPermissions((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]));
  }

  async function publish() {
    if (!name.trim() || !description.trim()) return;
    setSubmitting(true);
    try {
      const manifest = { name, version, entry_point: entryPoint, description, permissions: selectedPermissions };
      const manifestBlob = new Blob([JSON.stringify(manifest)], { type: "application/json" });
      const codeBlob = new Blob([codeText], { type: "text/plain" });
      const plugin = await createPlugin(orgId, {
        name, description, category, pricing, price: pricing !== "free" && price ? Number(price) : undefined,
        manifest: manifestBlob, code: codeBlob,
      });
      setName("");
      setDescription("");
      onPublished?.(plugin);
    } catch (err) {
      onError?.(err instanceof ApiError ? String(err.detail) : "Failed to publish plugin");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <h3 className="text-sm font-semibold text-foreground">Publish a new plugin</h3>
      <p className="mt-1 text-xs text-foreground-muted">Reviewed by an admin before it appears in the marketplace.</p>

      <div className="mt-3 flex flex-col gap-2">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Plugin name" className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-accent" />
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description" rows={2} className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-accent" />
        <div className="flex gap-2">
          <select value={category} onChange={(e) => setCategory(e.target.value)} className="w-1/3 rounded-lg border border-border bg-background px-3 py-1.5 text-sm">
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="Version (e.g. 1.0.0)" className="w-1/3 rounded-lg border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-accent" />
          <select value={entryPoint} onChange={(e) => setEntryPoint(e.target.value)} className="w-1/3 rounded-lg border border-border bg-background px-3 py-1.5 text-sm">
            <option value="index.js">index.js</option>
            <option value="index.py">index.py</option>
          </select>
        </div>

        <div className="flex gap-2">
          <select value={pricing} onChange={(e) => setPricing(e.target.value)} className="w-1/2 rounded-lg border border-border bg-background px-3 py-1.5 text-sm">
            <option value="free">Free</option>
            <option value="paid">Paid</option>
            <option value="freemium">Freemium</option>
          </select>
          {pricing !== "free" && (
            <input
              value={price} onChange={(e) => setPrice(e.target.value)} placeholder="Price (EUR)" type="number" min="0.01" step="0.01"
              className="w-1/2 rounded-lg border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-accent"
            />
          )}
        </div>

        <div>
          <p className="text-xs font-medium text-foreground-muted">Permissions</p>
          <div className="mt-1 flex flex-wrap gap-2">
            {permissions.map((p) => (
              <label key={p.id} className="flex items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1 text-xs">
                <input type="checkbox" checked={selectedPermissions.includes(p.id)} onChange={() => togglePermission(p.id)} />
                {p.label}
              </label>
            ))}
          </div>
        </div>

        <textarea
          value={codeText}
          onChange={(e) => setCodeText(e.target.value)}
          rows={6}
          className="rounded-lg border border-border bg-background px-3 py-1.5 font-mono text-xs outline-none focus:border-accent"
        />

        <button
          type="button"
          disabled={submitting || !name.trim() || !description.trim()}
          onClick={() => void publish()}
          className="self-start rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {submitting ? "Publishing…" : "Publish"}
        </button>
      </div>
    </div>
  );
}
