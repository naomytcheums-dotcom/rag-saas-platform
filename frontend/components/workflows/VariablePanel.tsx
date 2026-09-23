"use client";

// Phase 5, Étape 5 -- variable CRUD. Shape matches
// api/models/workflow.py's own real `variables` column
// ({name, type, default_value, description, scope}) exactly.

export interface WorkflowVariable {
  name: string;
  type: "string" | "number" | "boolean" | "object" | "array";
  default_value?: unknown;
  description?: string;
  scope: "global" | "node";
}

interface Props {
  variables: WorkflowVariable[];
  onChange: (variables: WorkflowVariable[]) => void;
}

const EMPTY_VARIABLE: WorkflowVariable = { name: "", type: "string", default_value: "", description: "", scope: "global" };

export function VariablePanel({ variables, onChange }: Props) {
  const addVariable = () => onChange([...variables, { ...EMPTY_VARIABLE }]);
  const updateVariable = (index: number, patch: Partial<WorkflowVariable>) =>
    onChange(variables.map((v, i) => (i === index ? { ...v, ...patch } : v)));
  const removeVariable = (index: number) => onChange(variables.filter((_, i) => i !== index));

  return (
    <div className="border-t border-border p-3" data-testid="variable-panel">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-foreground">Variables</h3>
        <button type="button" onClick={addVariable} className="text-xs text-accent hover:text-accent-hover" data-testid="add-variable">
          + Ajouter
        </button>
      </div>
      <ul className="mt-2 space-y-2">
        {variables.map((variable, index) => (
          <li key={index} className="flex items-center gap-1 text-xs">
            <input
              className="w-24 rounded border border-border bg-surface px-1.5 py-1"
              placeholder="nom"
              value={variable.name}
              onChange={(e) => updateVariable(index, { name: e.target.value })}
              data-testid={`variable-name-${index}`}
            />
            <select
              className="rounded border border-border bg-surface px-1 py-1"
              value={variable.type}
              onChange={(e) => updateVariable(index, { type: e.target.value as WorkflowVariable["type"] })}
            >
              <option value="string">string</option>
              <option value="number">number</option>
              <option value="boolean">boolean</option>
              <option value="object">object</option>
              <option value="array">array</option>
            </select>
            <input
              className="w-20 rounded border border-border bg-surface px-1.5 py-1"
              placeholder="défaut"
              value={variable.default_value != null ? String(variable.default_value) : ""}
              onChange={(e) => updateVariable(index, { default_value: e.target.value })}
            />
            <button type="button" onClick={() => removeVariable(index)} className="text-danger hover:text-danger" aria-label={`Supprimer ${variable.name || "variable"}`}>
              ✕
            </button>
          </li>
        ))}
        {variables.length === 0 && <li className="text-xs text-foreground-muted">Aucune variable définie.</li>}
      </ul>
    </div>
  );
}
