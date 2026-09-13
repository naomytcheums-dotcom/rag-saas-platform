"use client";

import { useEffect, useState } from "react";
import * as autonomousAgentsService from "@/lib/services/autonomous-agents";
import type { AgentCollaboration } from "@/lib/services/autonomous-agents";

export function AgentCollaborationView({ agentId }: { agentId: string }) {
  const [collaboratorId, setCollaboratorId] = useState("");
  const [task, setTask] = useState("");
  const [collaborations, setCollaborations] = useState<AgentCollaboration[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = () => {
    autonomousAgentsService.listCollaborations(agentId).then(setCollaborations).catch(() => setCollaborations([]));
  };

  useEffect(reload, [agentId]);

  const submit = async () => {
    if (!collaboratorId.trim() || !task.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await autonomousAgentsService.collaborateAgents(agentId, { collaborator_agent_id: collaboratorId, task });
      setCollaboratorId(""); setTask("");
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Collaboration failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-3">
        <input value={collaboratorId} onChange={(e) => setCollaboratorId(e.target.value)} placeholder="Collaborator agent id" className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
        <input value={task} onChange={(e) => setTask(e.target.value)} placeholder="Task to delegate" className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
        {error && <p className="text-xs text-danger">{error}</p>}
        <button type="button" onClick={() => void submit()} disabled={submitting} className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
          {submitting ? "Collaborating…" : "Request collaboration"}
        </button>
      </div>
      <div className="flex flex-col gap-2">
        {collaborations.map((collab) => (
          <div key={collab.id} className="rounded-lg border border-border bg-surface p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-foreground">{collab.task}</span>
              <span className="text-xs text-foreground-muted">{collab.status}</span>
            </div>
            {collab.result && <p className="mt-1 text-xs text-foreground-muted">{JSON.stringify(collab.result)}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
