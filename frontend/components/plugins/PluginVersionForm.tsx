"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { publishVersion } from "@/lib/services/plugins";
import type { Plugin } from "@/lib/types";

interface PluginVersionFormProps {
  orgId: string;
  plugin: Plugin;
  onPublished?: (plugin: Plugin) => void;
  onError?: (message: string) => void;
}

// Partie 16 (ter) -- PUT /organizations/{org_id}/plugins/{id}: a real
// new PluginVersion row, and resets moderation status back to
// `pending` (a code/manifest change is always re-reviewed).
export default function PluginVersionForm({ orgId, plugin, onPublished, onError }: PluginVersionFormProps) {
  const [version, setVersion] = useState("");
  const [changelog, setChangelog] = useState("");
  const [codeText, setCodeText] = useState("// your updated plugin code here\n");
  const [submitting, setSubmitting] = useState(false);

  async function publish() {
    if (!version.trim()) return;
    setSubmitting(true);
    try {
      const manifest = { ...plugin.manifest, version };
      const manifestBlob = new Blob([JSON.stringify(manifest)], { type: "application/json" });
      const codeBlob = new Blob([codeText], { type: "text/plain" });
      const updated = await publishVersion(orgId, plugin.id, { changelog: changelog || undefined, manifest: manifestBlob, code: codeBlob });
      setVersion("");
      setChangelog("");
      onPublished?.(updated);
    } catch (err) {
      onError?.(err instanceof ApiError ? String(err.detail) : "Failed to publish this version");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-background p-3 text-xs">
      <h4 className="font-medium text-foreground">Publish a new version (current: v{plugin.version})</h4>
      <div className="mt-2 flex flex-col gap-2">
        <input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="New version (e.g. 1.1.0)" className="rounded-lg border border-border bg-surface px-2.5 py-1 text-xs outline-none focus:border-accent" />
        <input value={changelog} onChange={(e) => setChangelog(e.target.value)} placeholder="Changelog (optional)" className="rounded-lg border border-border bg-surface px-2.5 py-1 text-xs outline-none focus:border-accent" />
        <textarea value={codeText} onChange={(e) => setCodeText(e.target.value)} rows={5} className="rounded-lg border border-border bg-surface px-2.5 py-1 font-mono text-xs outline-none focus:border-accent" />
        <button type="button" disabled={submitting || !version.trim()} onClick={() => void publish()} className="self-start rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50">
          {submitting ? "Publishing…" : "Publish version"}
        </button>
      </div>
    </div>
  );
}
