"use client";

import { useState } from "react";
import * as autonomousAgentsService from "@/lib/services/autonomous-agents";
import type { AutonomousAgent } from "@/lib/services/autonomous-agents";

const FILTER_LEVELS = ["low", "medium", "high"];

export function AgentGuardrailsConfig({ agent, onSaved }: { agent: AutonomousAgent; onSaved: (agent: AutonomousAgent) => void }) {
  const guardrails = agent.guardrails as { blocked_topics?: string[]; content_filter_level?: string };
  const [blockedTopics, setBlockedTopics] = useState((guardrails.blocked_topics ?? []).join(", "));
  const [filterLevel, setFilterLevel] = useState(guardrails.content_filter_level ?? "medium");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await autonomousAgentsService.updateAutonomousAgent(agent.id, {
        guardrails: {
          ...agent.guardrails,
          blocked_topics: blockedTopics.split(",").map((t) => t.trim()).filter(Boolean),
          content_filter_level: filterLevel,
        },
      });
      onSaved(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save guardrails");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-3">
      <label className="flex flex-col gap-1 text-xs text-foreground-muted">
        Blocked topics (comma-separated)
        <input value={blockedTopics} onChange={(e) => setBlockedTopics(e.target.value)} className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
      </label>
      <label className="flex flex-col gap-1 text-xs text-foreground-muted">
        Content filter level
        <select value={filterLevel} onChange={(e) => setFilterLevel(e.target.value)} className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground">
          {FILTER_LEVELS.map((level) => <option key={level} value={level}>{level}</option>)}
        </select>
      </label>
      {error && <p className="text-xs text-danger">{error}</p>}
      <button type="button" onClick={() => void save()} disabled={saving} className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {saving ? "Saving…" : "Save guardrails"}
      </button>
    </div>
  );
}
