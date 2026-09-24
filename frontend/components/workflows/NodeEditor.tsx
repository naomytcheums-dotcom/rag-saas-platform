"use client";

// Phase 5, Étape 5 -- the real node config editor. Field names match
// the REAL backend block config keys exactly (api/services/workflow_block_*.py's
// own `block_config["..."]` reads, verified against each module before
// writing this) -- not invented client-side field names that would
// silently no-op at execution time.

import type { WorkflowNode, WorkflowNodeType } from "@/lib/services/workflows";

interface Props {
  node: WorkflowNode;
  allNodeIds: string[];
  onChange: (data: Record<string, unknown>) => void;
  onClose: () => void;
  onDelete: () => void;
}

function TextField({ label, value, onChange, multiline }: { label: string; value: string; onChange: (v: string) => void; multiline?: boolean }) {
  return (
    <label className="block text-xs">
      <span className="font-medium text-foreground">{label}</span>
      {multiline ? (
        <textarea
          className="mt-1 w-full rounded-md border border-border bg-surface p-2 text-sm text-foreground"
          rows={3}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          className="mt-1 w-full rounded-md border border-border bg-surface p-2 text-sm text-foreground"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </label>
  );
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <label className="block text-xs">
      <span className="font-medium text-foreground">{label}</span>
      <select className="mt-1 w-full rounded-md border border-border bg-surface p-2 text-sm text-foreground" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
    </label>
  );
}

function fieldsFor(type: WorkflowNodeType, data: Record<string, unknown>, set: (key: string, value: unknown) => void, allNodeIds: string[]) {
  const str = (key: string) => (typeof data[key] === "string" ? (data[key] as string) : "");

  switch (type) {
    case "llm_call":
      return (
        <>
          <TextField label="Prompt utilisateur ({{ variable }} supporté)" value={str("user_prompt")} onChange={(v) => set("user_prompt", v)} multiline />
          <TextField label="Modèle (optionnel)" value={str("model")} onChange={(v) => set("model", v)} />
        </>
      );
    case "rag_search":
      return (
        <>
          <TextField label="Base de connaissances (ID)" value={str("knowledge_base_id")} onChange={(v) => set("knowledge_base_id", v)} />
          <TextField label="Requête ({{ variable }} supporté)" value={str("query")} onChange={(v) => set("query", v)} />
        </>
      );
    case "web_search":
    case "database":
      return <TextField label="Requête" value={str("query")} onChange={(v) => set("query", v)} />;
    case "http_call":
      return (
        <>
          <TextField label="URL" value={str("url")} onChange={(v) => set("url", v)} />
          <SelectField label="Méthode" value={str("method") || "GET"} options={["GET", "POST", "PUT", "PATCH", "DELETE"]} onChange={(v) => set("method", v)} />
        </>
      );
    case "condition":
      return (
        <>
          <TextField label="Expression (ex: score > 0.8)" value={str("condition")} onChange={(v) => set("condition", v)} />
          <SelectField label="Branche si vrai" value={str("true_branch")} options={["", ...allNodeIds]} onChange={(v) => set("true_branch", v)} />
          <SelectField label="Branche si faux" value={str("false_branch")} options={["", ...allNodeIds]} onChange={(v) => set("false_branch", v)} />
        </>
      );
    case "code":
      return (
        <>
          <SelectField label="Langage" value={str("language") || "python"} options={["python"]} onChange={(v) => set("language", v)} />
          <TextField label="Code" value={str("code")} onChange={(v) => set("code", v)} multiline />
        </>
      );
    case "email":
      return (
        <>
          <TextField label="Destinataire(s), séparés par une virgule" value={str("to")} onChange={(v) => set("to", v)} />
          <TextField label="Sujet" value={str("subject")} onChange={(v) => set("subject", v)} />
          <TextField label="Corps ({{ variable }} supporté)" value={str("body")} onChange={(v) => set("body", v)} multiline />
        </>
      );
    case "calendar":
      return (
        <>
          <SelectField label="Action" value={str("action") || "create"} options={["create", "update", "delete", "find_slots"]} onChange={(v) => set("action", v)} />
          <TextField label="Titre" value={str("title")} onChange={(v) => set("title", v)} />
        </>
      );
    case "human": {
      const inputType = str("input_type") || "text";
      const rawOptions = data.choices;
      const choices: string[] = Array.isArray(rawOptions) ? rawOptions.map((c) => String(c)) : ["", ""];

      function updateChoice(index: number, value: string) {
        const next = [...choices];
        next[index] = value;
        set("choices", next);
      }

      function addChoice() {
        set("choices", [...choices, ""]);
      }

      function removeChoice(index: number) {
        set("choices", choices.filter((_, i) => i !== index));
      }

      return (
        <>
          <TextField label="Message ({{ variable }} supporté)" value={str("message")} onChange={(v) => set("message", v)} multiline />
          <SelectField label="Type de réponse" value={inputType} options={["text", "confirm", "choice"]} onChange={(v) => set("input_type", v)} />
          <TextField label="Label du bouton d'approbation" value={str("approve_label") || "Approuver"} onChange={(v) => set("approve_label", v)} />
          <TextField label="Label du bouton de rejet" value={str("reject_label") || "Rejeter"} onChange={(v) => set("reject_label", v)} />
          <TextField label="Timeout (secondes, vide = pas de timeout)" value={str("timeout_seconds") || ""} onChange={(v) => set("timeout_seconds", v)} />

          {inputType === "choice" ? (
            <div className="rounded-md border border-border bg-background p-2">
              <p className="mb-2 text-xs font-medium text-foreground">Options de choix</p>
              {choices.map((choice, index) => (
                <div key={index} className="mb-1 flex gap-1">
                  <input
                    type="text"
                    value={choice}
                    onChange={(e) => updateChoice(index, e.target.value)}
                    placeholder={`Option ${index + 1}`}
                    className="flex-1 rounded-md border border-border bg-surface px-2 py-1 text-xs text-foreground"
                  />
                  <button
                    type="button"
                    onClick={() => removeChoice(index)}
                    className="rounded-md border border-border px-2 py-1 text-xs text-danger hover:border-danger"
                    title="Supprimer cette option"
                  >
                    ×
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={addChoice}
                className="mt-1 w-full rounded-md border border-border px-2 py-1 text-xs text-foreground-muted hover:border-accent"
              >
                + Ajouter une option
              </button>
            </div>
          ) : null}
        </>
      );
    }
    default:
      return <p className="text-xs text-foreground-muted">Ce type de nœud n&apos;a pas de configuration.</p>;
  }
}

export function NodeEditor({ node, allNodeIds, onChange, onClose, onDelete }: Props) {
  const data = node.data ?? {};
  const set = (key: string, value: unknown) => onChange({ ...data, [key]: value });

  return (
    <aside className="flex w-80 flex-col gap-3 border-l border-border bg-surface p-4" data-testid="node-editor">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Éditer le nœud</h3>
        <button type="button" onClick={onClose} className="text-xs text-foreground-muted hover:text-foreground">
          Fermer
        </button>
      </div>
      <TextField label="Libellé" value={(data.label as string) || ""} onChange={(v) => set("label", v)} />
      {fieldsFor(node.type, data, set, allNodeIds)}
      <button
        type="button"
        onClick={onDelete}
        className="mt-2 rounded-md border border-danger px-3 py-1.5 text-xs font-medium text-danger hover:bg-danger-soft"
      >
        Supprimer ce nœud
      </button>
    </aside>
  );
}
