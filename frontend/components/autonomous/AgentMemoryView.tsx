"use client";

import { useEffect, useState } from "react";
import * as autonomousAgentsService from "@/lib/services/autonomous-agents";
import type { AgentMemory } from "@/lib/services/autonomous-agents";

const TYPES: { label: string; value: string | undefined }[] = [
  { label: "All", value: undefined }, { label: "Short-term", value: "short_term" }, { label: "Long-term", value: "long_term" }, { label: "Episodic", value: "episodic" },
];

export function AgentMemoryView({ agentId }: { agentId: string }) {
  const [memoryType, setMemoryType] = useState<string | undefined>(undefined);
  const [memories, setMemories] = useState<AgentMemory[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    autonomousAgentsService.getAgentMemory(agentId, memoryType).then(setMemories).catch(() => setMemories([])).finally(() => setLoading(false));
  }, [agentId, memoryType]);

  const remove = async (memoryId: string) => {
    await autonomousAgentsService.deleteAgentMemory(agentId, memoryId);
    setMemories((current) => current.filter((m) => m.id !== memoryId));
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        {TYPES.map((t) => (
          <button
            key={t.label} type="button" onClick={() => setMemoryType(t.value)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${memoryType === t.value ? "bg-accent text-white" : "bg-surface-muted text-foreground-muted hover:bg-accent-soft"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {loading && <p className="text-xs text-foreground-muted">Loading…</p>}
      {!loading && memories.length === 0 && <p className="text-xs text-foreground-muted">No memories yet.</p>}
      <div className="flex flex-col gap-2">
        {memories.map((memory) => (
          <div key={memory.id} className="flex items-start justify-between gap-2 rounded-lg border border-border bg-surface p-3">
            <div>
              <span className="text-xs font-medium text-foreground-muted">{memory.memory_type}</span>
              <p className="text-sm text-foreground">{memory.content}</p>
            </div>
            <button type="button" onClick={() => void remove(memory.id)} className="text-xs text-danger hover:underline">Delete</button>
          </div>
        ))}
      </div>
    </div>
  );
}
