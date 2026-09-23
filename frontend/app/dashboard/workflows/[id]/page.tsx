"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import LoadingState from "@/components/LoadingState";
import { WorkflowBuilder } from "@/components/workflows/WorkflowBuilder";
import * as workflowService from "@/lib/services/workflows";
import type { Workflow } from "@/lib/services/workflows";

export default function Page() {
  const params = useParams<{ id: string }>();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void workflowService
      .getWorkflow(params.id)
      .then(setWorkflow)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load workflow"));
  }, [params.id]);

  if (error) return <p className="text-sm text-danger">{error}</p>;
  if (!workflow) return <LoadingState fullScreen={false} />;

  return (
    <div>
      <h1 className="mb-3 text-xl font-semibold text-foreground">{workflow.name}</h1>
      <WorkflowBuilder workflow={workflow} onSaved={setWorkflow} />
    </div>
  );
}
