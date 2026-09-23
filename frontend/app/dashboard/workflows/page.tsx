"use client";

import Link from "next/link";
import { useState } from "react";
import LoadingState from "@/components/LoadingState";
import { useWorkflows } from "@/lib/hooks/useWorkflows";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import * as workflowService from "@/lib/services/workflows";

export default function Page() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const { workflows, loading } = useWorkflows(org?.id ?? "");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (orgLoading || !org) return <LoadingState fullScreen={false} />;

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      const workflow = await workflowService.createWorkflow(org.id, {
        name: "Nouveau workflow",
        nodes: [{ id: "trigger", type: "trigger", position: { x: 0, y: 0 } }],
        edges: [],
      });
      window.location.href = `/dashboard/workflows/${workflow.id}`;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create workflow");
      setCreating(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Workflows</h1>
          <p className="mt-1 text-sm text-foreground-muted">Automatisez des tâches avec un canvas visuel (React Flow).</p>
        </div>
        <button
          type="button"
          onClick={() => void handleCreate()}
          disabled={creating}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {creating ? "Création…" : "+ Nouveau workflow"}
        </button>
      </div>
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}

      {loading ? (
        <LoadingState fullScreen={false} />
      ) : workflows.length === 0 ? (
        <p className="mt-6 text-sm text-foreground-muted">Aucun workflow pour le moment.</p>
      ) : (
        <ul className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {workflows.map((workflow) => (
            <li key={workflow.id}>
              <Link href={`/dashboard/workflows/${workflow.id}`} className="block rounded-xl border border-border bg-surface p-4 hover:border-accent">
                <p className="text-sm font-medium text-foreground">{workflow.name}</p>
                <p className="mt-1 text-xs text-foreground-muted">{workflow.nodes.length} nœud(s) · {workflow.status}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
