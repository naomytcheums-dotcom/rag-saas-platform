"use client";

import { useRef, useState } from "react";
import { NODE_TYPE_OPTIONS } from "@/components/workflows/nodeTypes";
import { WORKFLOW_TEMPLATES } from "@/components/workflows/templates";
import type { WorkflowNodeType } from "@/lib/services/workflows";

interface Props {
  onAddNode: (type: WorkflowNodeType) => void;
  onSave: () => void;
  saving: boolean;
  onExport: () => void;
  onImport: (file: File) => void;
  onUseTemplate: (templateId: string) => void;
  onUndo: () => void;
  onRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  validationErrors: string[];
  validationWarnings: string[];
}

export function Toolbar({ onAddNode, onSave, saving, onExport, onImport, onUseTemplate, onUndo, onRedo, canUndo, canRedo, validationErrors, validationWarnings }: Props) {
  const [showTemplates, setShowTemplates] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex flex-col gap-2 border-b border-border bg-surface p-3" data-testid="workflow-toolbar">
      <div className="flex flex-wrap items-center gap-2">
        <select
          className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-foreground"
          defaultValue=""
          onChange={(e) => {
            if (e.target.value) onAddNode(e.target.value as WorkflowNodeType);
            e.target.value = "";
          }}
          data-testid="add-node-select"
        >
          <option value="" disabled>+ Ajouter un nœud</option>
          {NODE_TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        <button
          type="button"
          onClick={onUndo}
          disabled={!canUndo}
          className="rounded-md border border-border px-3 py-1 text-xs text-foreground hover:border-accent disabled:opacity-30"
          title="Annuler (Ctrl+Z)"
          data-testid="undo-button"
        >
          ↶ Annuler
        </button>

        <button
          type="button"
          onClick={onRedo}
          disabled={!canRedo}
          className="rounded-md border border-border px-3 py-1 text-xs text-foreground hover:border-accent disabled:opacity-30"
          title="Rétablir (Ctrl+Y)"
          data-testid="redo-button"
        >
          ↷ Rétablir
        </button>

        <button type="button" onClick={onSave} disabled={saving} className="rounded-md bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50" data-testid="save-button">
          {saving ? "Enregistrement…" : "Enregistrer"}
        </button>

        <button type="button" onClick={onExport} className="rounded-md border border-border px-3 py-1 text-xs text-foreground hover:border-accent" data-testid="export-button">
          Exporter
        </button>

        <button type="button" onClick={() => fileInputRef.current?.click()} className="rounded-md border border-border px-3 py-1 text-xs text-foreground hover:border-accent" data-testid="import-button">
          Importer
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="application/json"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onImport(file);
            e.target.value = "";
          }}
        />

        <div className="relative">
          <button type="button" onClick={() => setShowTemplates((v) => !v)} className="rounded-md border border-border px-3 py-1 text-xs text-foreground hover:border-accent" data-testid="templates-button">
            Modèles
          </button>
          {showTemplates && (
            <ul className="absolute z-10 mt-1 w-64 rounded-md border border-border bg-surface p-1 shadow-lg">
              {WORKFLOW_TEMPLATES.map((template) => (
                <li key={template.id}>
                  <button
                    type="button"
                    onClick={() => {
                      onUseTemplate(template.id);
                      setShowTemplates(false);
                    }}
                    className="block w-full rounded px-2 py-1.5 text-left text-xs hover:bg-surface-muted"
                    data-testid={`use-template-${template.id}`}
                  >
                    <span className="font-medium text-foreground">{template.name}</span>
                    <span className="block text-[11px] text-foreground-muted">{template.description}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {validationErrors.length > 0 && (
        <ul className="text-xs text-danger" data-testid="validation-errors">
          {validationErrors.map((err, i) => <li key={i}>⚠ {err}</li>)}
        </ul>
      )}
      {validationWarnings.length > 0 && (
        <ul className="text-xs text-warning" data-testid="validation-warnings">
          {validationWarnings.map((warn, i) => <li key={i}>ℹ {warn}</li>)}
        </ul>
      )}
    </div>
  );
}
