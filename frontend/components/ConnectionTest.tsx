"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { ConnectionTestResult } from "@/lib/types";

interface ConnectionTestProps {
  orgId: string;
  connectionId: string;
}

// Partie 15.1 -- POST /organizations/{org_id}/integrations/connections/{id}/test
// (api/services/integrations.py's own test_connection: a real dry run
// against a synthetic sample payload, never actually runs the action).
export default function ConnectionTest({ orgId, connectionId }: ConnectionTestProps) {
  const [result, setResult] = useState<ConnectionTestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function runTest() {
    setRunning(true);
    setError(null);
    try {
      setResult(await api.post<ConnectionTestResult>(`/organizations/${orgId}/integrations/connections/${connectionId}/test`));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Test failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-background p-3 text-xs">
      <div className="flex items-center justify-between">
        <h4 className="font-medium text-foreground">Test connection</h4>
        <button type="button" onClick={() => void runTest()} disabled={running} className="rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50">
          {running ? "Running…" : "Run test"}
        </button>
      </div>

      {error && <p className="mt-2 text-danger">{error}</p>}

      {result && (
        <div className="mt-2 flex flex-col gap-1 text-foreground-muted">
          <p>Connection active: <span className="text-foreground">{String(result.connection_active)}</span></p>
          <p>Would run action: <span className="text-foreground">{result.would_run_action}</span></p>
          <p className="mt-1 font-medium text-foreground">Sample payload → mapped:</p>
          <pre className="overflow-x-auto rounded bg-surface p-2 font-mono">{JSON.stringify(result.sample_payload, null, 2)}</pre>
          <pre className="overflow-x-auto rounded bg-surface p-2 font-mono">{JSON.stringify(result.mapped_payload, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
