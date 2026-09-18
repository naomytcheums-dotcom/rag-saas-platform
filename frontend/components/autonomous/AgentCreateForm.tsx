"use client";

import { useState } from "react";
import { useAutonomousAgents } from "@/lib/hooks/useAutonomousAgents";

interface AgentCreateFormProps {
  orgId: string;
  onCreated: () => void;
}

export function AgentCreateForm({ orgId, onCreated }: AgentCreateFormProps) {
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
      setError(err instanceof Error ? err.message : "Échec de la création de l'agent");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nom de l'agent" className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
      <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description (facultatif)" className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
      <textarea value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="Objectif — que doit accomplir cet agent ?" rows={3} className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
      <label className="flex items-center gap-2 text-xs text-foreground-muted">
        Étapes maximum
        <input type="number" min={1} value={maxSteps} onChange={(e) => setMaxSteps(Number(e.target.value))} className="w-20 rounded-lg border border-border bg-background px-2 py-1 text-sm text-foreground" />
      </label>
      {error && <p className="text-xs text-danger">{error}</p>}
      <button type="button" onClick={() => void submit()} disabled={submitting} className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {submitting ? "Création…" : "Créer l'agent"}
      </button>
    </div>
  );
}
