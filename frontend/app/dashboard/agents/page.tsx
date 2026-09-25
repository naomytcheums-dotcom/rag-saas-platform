"use client";

import LoadingState from "@/components/LoadingState";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

interface Agent {
  id: string;
  name: string;
  description: string | null;
  status: string;
}

export default function AgentsPage() {
  const { org } = useCurrentOrg();
  const { t } = useTranslation();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!org) return;
    setLoading(true);
    try {
      setAgents(await api.get<Agent[]>(`/organizations/${org.id}/agents`));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("agents.error_load"));
    } finally {
      setLoading(false);
    }
  }, [org]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  useEffect(() => {
    if (!systemPrompt) setSystemPrompt(t("agents.default_prompt"));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on mount
  }, []);

  async function createAgent() {
    if (!org || !name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await api.post(`/organizations/${org.id}/agents`, { name, description: description || null, system_prompt: systemPrompt });
      setName("");
      setDescription("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("agents.error_create"));
    } finally {
      setCreating(false);
    }
  }

  async function removeAgent(id: string) {
    await api.delete(`/agents/${id}`);
    await load();
  }

  async function toggleStatus(agent: Agent) {
    const action = agent.status === "active" ? "pause" : "activate";
    await api.post(`/agents/${agent.id}/${action}`);
    await load();
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-xl font-semibold text-foreground">{t("agents.title")}</h1>
      <p className="mt-1 text-sm text-foreground-muted">{t("agents.subtitle")}</p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      <div className="mt-6 rounded-xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-foreground">{t("agents.create_heading")}</h2>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("agents.name_placeholder")} className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
        <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder={t("agents.description_placeholder")} className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
        <textarea value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} rows={3} className="mt-2 w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
        <button type="button" onClick={() => void createAgent()} disabled={creating || !name.trim()} className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
          {creating ? t("agents.creating") : t("agents.create_button")}
        </button>
      </div>

      <div className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-foreground">{t("agents.your_agents")}</h2>
        {loading ? (
          <LoadingState fullScreen={false} />
        ) : agents.length === 0 ? (
          <p className="text-sm text-foreground-muted">{t("agents.empty")}</p>
        ) : (
          <div className="flex flex-col gap-2">
            {agents.map((agent) => (
              <div key={agent.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3">
                <div>
                  <p className="text-sm font-medium text-foreground">{agent.name}</p>
                  <p className="text-xs text-foreground-muted">{agent.description ?? t("agents.no_description")} · {agent.status}</p>
                </div>
                <div className="flex items-center gap-3">
                  <button type="button" onClick={() => void toggleStatus(agent)} className="text-xs font-medium text-accent hover:underline">
                    {agent.status === "active" ? t("agents.pause") : t("agents.activate")}
                  </button>
                  <button type="button" onClick={() => void removeAgent(agent.id)} className="text-xs font-medium text-danger hover:underline">{t("agents.delete")}</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
