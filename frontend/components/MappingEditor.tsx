"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { IntegrationMapping } from "@/lib/types";

interface MappingEditorProps {
  orgId: string;
  connectionId: string;
  existing?: IntegrationMapping; // present -> edit (PATCH), absent -> create (POST)
  onSaved: (mapping: IntegrationMapping) => void;
  onCancel?: () => void;
  onError: (message: string) => void;
}

const TRANSFORMS = ["", "normalize_email", "normalize_phone", "normalize_date"];

// Partie 15.1 -- POST .../mappings (create) and the previously-missing
// PATCH .../mappings/{id} (edit), api/routers/integrations_universal.py.
export default function MappingEditor({ orgId, connectionId, existing, onSaved, onCancel, onError }: MappingEditorProps) {
  const [sourceField, setSourceField] = useState(existing?.source_field ?? "");
  const [targetField, setTargetField] = useState(existing?.target_field ?? "");
  const [transform, setTransform] = useState(existing?.transform ?? "");
  const [saving, setSaving] = useState(false);

  async function save() {
    if (!sourceField.trim() || !targetField.trim()) return;
    setSaving(true);
    try {
      const body = { source_field: sourceField, target_field: targetField, transform: transform || null };
      const saved = existing
        ? await api.patch<IntegrationMapping>(`/organizations/${orgId}/integrations/mappings/${existing.id}`, body)
        : await api.post<IntegrationMapping>(`/organizations/${orgId}/integrations/connections/${connectionId}/mappings`, body);
      if (!existing) {
        setSourceField("");
        setTargetField("");
        setTransform("");
      }
      onSaved(saved);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to save mapping");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input value={sourceField} onChange={(e) => setSourceField(e.target.value)} placeholder="Source field" className="rounded-lg border border-border bg-background px-2.5 py-1 text-xs outline-none focus:border-accent" />
      <span className="text-foreground-muted">→</span>
      <input value={targetField} onChange={(e) => setTargetField(e.target.value)} placeholder="Target field" className="rounded-lg border border-border bg-background px-2.5 py-1 text-xs outline-none focus:border-accent" />
      <select value={transform} onChange={(e) => setTransform(e.target.value)} className="rounded-lg border border-border bg-background px-2.5 py-1 text-xs">
        {TRANSFORMS.map((t) => (
          <option key={t} value={t}>{t || "No transform"}</option>
        ))}
      </select>
      <button type="button" disabled={saving} onClick={() => void save()} className="rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {saving ? "Saving…" : existing ? "Save" : "Add"}
      </button>
      {onCancel && (
        <button type="button" onClick={onCancel} className="text-xs font-medium text-foreground-muted hover:underline">Cancel</button>
      )}
    </div>
  );
}
