"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { updateInstallationConfig } from "@/lib/services/plugins";
import type { PluginInstallation } from "@/lib/types";

interface PluginConfigFormProps {
  orgId: string;
  installation: PluginInstallation;
  onSaved?: () => void;
  onError?: (message: string) => void;
}

// Partie 16 (ter) -- PATCH .../installed/{id} with a real per-
// installation config JSON object (manifest.config_schema describes
// its real shape; this form edits it as raw JSON rather than
// generating a dynamic form from that schema, the fastest real
// approach for a config object nothing else in this pass validates
// against the schema either).
export default function PluginConfigForm({ orgId, installation, onSaved, onError }: PluginConfigFormProps) {
  const [text, setText] = useState(JSON.stringify(installation.config, null, 2));
  const [saving, setSaving] = useState(false);

  async function save() {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(text);
    } catch {
      onError?.("Config must be valid JSON");
      return;
    }
    setSaving(true);
    try {
      await updateInstallationConfig(orgId, installation.id, parsed);
      onSaved?.();
    } catch (err) {
      onError?.(err instanceof ApiError ? String(err.detail) : "Failed to save config");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={5}
        className="rounded-lg border border-border bg-background px-3 py-1.5 font-mono text-xs outline-none focus:border-accent"
      />
      <button type="button" disabled={saving} onClick={() => void save()} className="self-start rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {saving ? "Saving…" : "Save config"}
      </button>
    </div>
  );
}
