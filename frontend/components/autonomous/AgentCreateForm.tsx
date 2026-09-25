"use client";

import { useState } from "react";
import { useAutonomousAgents } from "@/lib/hooks/useAutonomousAgents";
import { useTranslation } from "@/lib/i18n";

interface AgentCreateFormProps {
  orgId: string;
  onCreated: () => void;
}

export function AgentCreateForm({ orgId, onCreated }: AgentCreateFormProps) {
  const { t } = useTranslation();
  const { create } = useAutonomousAgents(orgId);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [goal, setGoal] = useState("");
  const [maxSteps, setMaxSteps] = useState(20);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!name.trim() || !goal.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await create({ name, description: description || undefined, goal, max_steps: maxSteps });
      setName(""); setDescription(""); setGoal(""); setMaxSteps(20);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("agent_create.error_generic"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <input value={name} onChange={(e) => setName(e.target.value)} aria-label={t("agent_create.name_label")} placeholder={t("agent_create.name_placeholder")} className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
      <input value={description} onChange={(e) => setDescription(e.target.value)} aria-label={t("agent_create.description_label")} placeholder={t("agent_create.description_placeholder")} className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
      <textarea value={goal} onChange={(e) => setGoal(e.target.value)} aria-label={t("agent_create.goal_label")} placeholder={t("agent_create.goal_placeholder")} rows={3} className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
      <label className="flex items-center gap-2 text-xs text-foreground-muted">
        {t("agent_create.max_steps")}
        <input type="number" min={1} value={maxSteps} onChange={(e) => setMaxSteps(Number(e.target.value))} className="w-20 rounded-lg border border-border bg-background px-2 py-1 text-sm text-foreground" />
      </label>
      {error && <p className="text-xs text-danger">{error}</p>}
      <button type="button" onClick={() => void submit()} disabled={submitting} className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {submitting ? t("agent_create.submitting") : t("agent_create.submit")}
      </button>
    </div>
  );
}
