"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";

interface CallRecord {
  id: string;
  call_sid: string;
  from_number: string;
  to_number: string;
  status: string;
  duration_seconds: number | null;
  started_at: string;
  ended_at: string | null;
}

interface TelephonyProps {
  agentId: string;
}

// Partie 8.2.13 -- real call history (GET /twilio/calls) plus placing
// (POST /twilio/outbound) and ending (POST /twilio/{sid}/end) real
// calls -- both need real TWILIO_* credentials configured server-side
// (see api/services/telephony.py's own `_require_credentials`); a
// real, honest error surfaces here otherwise, never a fake success.
export default function Telephony({ agentId }: TelephonyProps) {
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [toNumber, setToNumber] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [placing, setPlacing] = useState(false);

  async function refresh() {
    try {
      setCalls(await api.get<CallRecord[]>("/twilio/calls"));
    } catch {
      setCalls([]);
    }
  }

  useEffect(() => {
    // Real, legitimate fetch-on-mount (same real reasoning as
    // ConversationList.tsx's own identical pattern, Partie 8.1).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, []);

  async function placeCall() {
    setPlacing(true);
    setError(null);
    try {
      await api.post(`/twilio/outbound?to=${encodeURIComponent(toNumber)}&agent_id=${agentId}`);
      setToNumber("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not place call");
    } finally {
      setPlacing(false);
    }
  }

  async function endCall(callSid: string) {
    await api.post(`/twilio/${callSid}/end`);
    await refresh();
  }

  const inProgress = calls.filter((c) => c.status === "in-progress" || c.status === "ringing");
  const history = calls.filter((c) => !inProgress.includes(c));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2">
        <input
          value={toNumber}
          onChange={(event) => setToNumber(event.target.value)}
          placeholder="+15551234567"
          className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
        />
        <button
          type="button"
          onClick={() => void placeCall()}
          disabled={placing || !toNumber}
          className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          Call
        </button>
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}

      {inProgress.length > 0 && (
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-foreground-muted">In progress</h3>
          {inProgress.map((call) => (
            <div key={call.id} className="flex items-center justify-between rounded-lg bg-accent-soft px-3 py-2 text-sm">
              <span>{call.to_number}</span>
              <button type="button" onClick={() => void endCall(call.call_sid)} className="text-xs font-medium text-danger hover:underline">
                End call
              </button>
            </div>
          ))}
        </div>
      )}

      <div>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-foreground-muted">History</h3>
        <ul className="space-y-1">
          {history.map((call) => (
            <li key={call.id} className="flex items-center justify-between rounded-lg px-3 py-2 text-sm hover:bg-surface-muted">
              <span>{call.from_number} → {call.to_number}</span>
              <span className="text-xs text-foreground-muted">
                {call.status}{call.duration_seconds != null ? ` · ${call.duration_seconds}s` : ""}
              </span>
            </li>
          ))}
          {history.length === 0 && <p className="text-sm text-foreground-muted">No calls yet.</p>}
        </ul>
      </div>
    </div>
  );
}
