"use client";

// Phase 5, Étape 5 -- the real node config editor. Field names match
// the REAL backend block config keys exactly (api/services/workflow_block_*.py's
// own `block_config["..."]` reads, verified against each module before
// writing this) -- not invented client-side field names that would
// silently no-op at execution time.

import type { WorkflowNode, WorkflowNodeType } from "@/lib/services/workflows";
import { useTranslation } from "@/lib/i18n";

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

function fieldsFor(type: WorkflowNodeType, data: Record<string, unknown>, set: (key: string, value: unknown) => void, allNodeIds: string[], t: (key: string, params?: Record<string, string | number>) => string) {
  const str = (key: string) => (typeof data[key] === "string" ? (data[key] as string) : "");

  switch (type) {
    case "llm_call":
      return (
        <>
          <TextField label={t("node_editor.llm_prompt")} value={str("user_prompt")} onChange={(v) => set("user_prompt", v)} multiline />
          <TextField label={t("node_editor.llm_model")} value={str("model")} onChange={(v) => set("model", v)} />
        </>
      );
    case "rag_search":
      return (
        <>
          <TextField label={t("node_editor.rag_kb")} value={str("knowledge_base_id")} onChange={(v) => set("knowledge_base_id", v)} />
          <TextField label={t("node_editor.rag_query")} value={str("query")} onChange={(v) => set("query", v)} />
        </>
      );
    case "web_search":
    case "database":
      return <TextField label={t("node_editor.query")} value={str("query")} onChange={(v) => set("query", v)} />;
    case "http_call":
      return (
        <>
          <TextField label={t("node_editor.url")} value={str("url")} onChange={(v) => set("url", v)} />
          <SelectField label={t("node_editor.method")} value={str("method") || "GET"} options={["GET", "POST", "PUT", "PATCH", "DELETE"]} onChange={(v) => set("method", v)} />
        </>
      );
    case "condition":
      return (
        <>
          <TextField label={t("node_editor.condition")} value={str("condition")} onChange={(v) => set("condition", v)} />
          <SelectField label={t("node_editor.true_branch")} value={str("true_branch")} options={["", ...allNodeIds]} onChange={(v) => set("true_branch", v)} />
          <SelectField label={t("node_editor.false_branch")} value={str("false_branch")} options={["", ...allNodeIds]} onChange={(v) => set("false_branch", v)} />
        </>
      );
    case "code":
      return (
        <>
          <SelectField label={t("node_editor.language")} value={str("language") || "python"} options={["python"]} onChange={(v) => set("language", v)} />
          <TextField label={t("node_editor.code")} value={str("code")} onChange={(v) => set("code", v)} multiline />
        </>
      );
    case "email":
      return (
        <>
          <TextField label={t("node_editor.email_to")} value={str("to")} onChange={(v) => set("to", v)} />
          <TextField label={t("node_editor.email_subject")} value={str("subject")} onChange={(v) => set("subject", v)} />
          <TextField label={t("node_editor.email_body")} value={str("body")} onChange={(v) => set("body", v)} multiline />
        </>
      );
    case "calendar":
      return (
        <>
          <SelectField label={t("node_editor.calendar_action")} value={str("action") || "create"} options={["create", "update", "delete", "find_slots"]} onChange={(v) => set("action", v)} />
          <TextField label={t("node_editor.calendar_title")} value={str("title")} onChange={(v) => set("title", v)} />
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
          <TextField label={t("node_editor.human_message")} value={str("message")} onChange={(v) => set("message", v)} multiline />
          <SelectField label={t("node_editor.human_input_type")} value={inputType} options={["text", "confirm", "choice"]} onChange={(v) => set("input_type", v)} />
          <TextField label={t("node_editor.human_approve_label")} value={str("approve_label") || t("node_editor.default_approve")} onChange={(v) => set("approve_label", v)} />
          <TextField label={t("node_editor.human_reject_label")} value={str("reject_label") || t("node_editor.default_reject")} onChange={(v) => set("reject_label", v)} />
          <TextField label={t("node_editor.human_timeout")} value={str("timeout_seconds") || ""} onChange={(v) => set("timeout_seconds", v)} />

          {inputType === "choice" ? (
            <div className="rounded-md border border-border bg-background p-2">
              <p className="mb-2 text-xs font-medium text-foreground">{t("node_editor.human_choices")}</p>
              {choices.map((choice, index) => (
                <div key={index} className="mb-1 flex gap-1">
                  <input
                    type="text"
                    value={choice}
                    onChange={(e) => updateChoice(index, e.target.value)}
                    placeholder={t("node_editor.human_option_placeholder", { number: index + 1 })}
                    className="flex-1 rounded-md border border-border bg-surface px-2 py-1 text-xs text-foreground"
                  />
                  <button
                    type="button"
                    onClick={() => removeChoice(index)}
                    className="rounded-md border border-border px-2 py-1 text-xs text-danger hover:border-danger"
                    title={t("node_editor.human_remove_option")}
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
                {t("node_editor.human_add_option")}
              </button>
            </div>
          ) : null}
        </>
      );
    }
    default:
      return <p className="text-xs text-foreground-muted">{t("node_editor.no_config")}</p>;
  }
}

export function NodeEditor({ node, allNodeIds, onChange, onClose, onDelete }: Props) {
  const { t } = useTranslation();
  const data = node.data ?? {};
  const set = (key: string, value: unknown) => onChange({ ...data, [key]: value });

  return (
    <aside className="flex w-80 flex-col gap-3 border-l border-border bg-surface p-4" data-testid="node-editor">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">{t("node_editor.title")}</h3>
        <button type="button" onClick={onClose} className="text-xs text-foreground-muted hover:text-foreground">
          {t("node_editor.close")}
        </button>
      </div>
      <TextField label={t("node_editor.label")} value={(data.label as string) || ""} onChange={(v) => set("label", v)} />
      {fieldsFor(node.type, data, set, allNodeIds, t)}
      <button
        type="button"
        onClick={onDelete}
        className="mt-2 rounded-md border border-danger px-3 py-1.5 text-xs font-medium text-danger hover:bg-danger-soft"
      >
        {t("node_editor.delete")}
      </button>
    </aside>
  );
}
