"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

interface IntegrationConfig {
  connected: boolean;
  [key: string]: unknown;
}

interface UniversalConnection {
  id: string;
  name: string;
  provider: string;
  action: string;
  is_active: boolean;
  token?: string;
}

function useIntegration(orgId: string | undefined, key: "slack" | "teams" | "discord") {
  const [config, setConfig] = useState<IntegrationConfig>({ connected: false });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    try {
      const data = await api.get(`/organizations/${orgId}/integrations/${key}/config`);
      setConfig({ connected: true, ...(data as object) });
    } catch {
      setConfig({ connected: false });
    } finally {
      setLoading(false);
    }
  }, [orgId, key]);

  useEffect(() => {
    void load();
  }, [load]);

  return { config, loading, reload: load };
}

export default function IntegrationsPage() {
  const { org } = useCurrentOrg();
  const slack = useIntegration(org?.id, "slack");
  const teams = useIntegration(org?.id, "teams");
  const discord = useIntegration(org?.id, "discord");
  const [error, setError] = useState<string | null>(null);

  async function connectSlack() {
    if (!org) return;
    try {
      const result = await api.get<{ url: string }>(`/organizations/${org.id}/integrations/slack/auth`);
      window.location.href = result.url;
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Slack is not configured on this instance yet");
    }
  }

  async function disconnect(key: "slack" | "teams" | "discord") {
    if (!org) return;
    await api.delete(`/organizations/${org.id}/integrations/${key}`);
    if (key === "slack") await slack.reload();
    if (key === "teams") await teams.reload();
    if (key === "discord") await discord.reload();
  }

  const [discordGuildId, setDiscordGuildId] = useState("");
  const [discordBotToken, setDiscordBotToken] = useState("");

  async function connectDiscord() {
    if (!org || !discordGuildId || !discordBotToken) return;
    try {
      await api.post(`/organizations/${org.id}/integrations/discord/configure`, { guild_id: discordGuildId, bot_token: discordBotToken });
      setDiscordGuildId("");
      setDiscordBotToken("");
      await discord.reload();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to connect Discord");
    }
  }

  const [teamsWebhookUrl, setTeamsWebhookUrl] = useState("");

  async function connectTeams() {
    if (!org || !teamsWebhookUrl) return;
    try {
      await api.post(`/organizations/${org.id}/integrations/teams/configure`, { webhook_url: teamsWebhookUrl });
      setTeamsWebhookUrl("");
      await teams.reload();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to connect Teams");
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-xl font-semibold text-foreground">Integrations</h1>
      <p className="mt-1 text-sm text-foreground-muted">Connect your chatbot to the platforms your team already uses.</p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      <div className="mt-6 flex flex-col gap-4">
        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-foreground">Slack</h2>
            </div>
            {slack.config.connected ? (
              <button type="button" onClick={() => void disconnect("slack")} className="text-xs font-medium text-danger hover:underline">Disconnect</button>
            ) : (
              <button type="button" onClick={() => void connectSlack()} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover">Connect</button>
            )}
          </div>
          <p className="mt-1 text-xs text-foreground-muted">{slack.loading ? "Checking…" : slack.config.connected ? "Connected" : "Not connected"}</p>
        </div>

        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-foreground">Microsoft Teams</h2>
          </div>
          <p className="mt-1 text-xs text-foreground-muted">{teams.loading ? "Checking…" : teams.config.connected ? "Connected" : "Not connected"}</p>
          {teams.config.connected ? (
            <button type="button" onClick={() => void disconnect("teams")} className="mt-2 text-xs font-medium text-danger hover:underline">Disconnect</button>
          ) : (
            <div className="mt-2 flex gap-2">
              <input value={teamsWebhookUrl} onChange={(e) => setTeamsWebhookUrl(e.target.value)} placeholder="Incoming webhook URL" className="flex-1 rounded-lg border border-border bg-background px-3 py-1.5 text-xs outline-none focus:border-accent" />
              <button type="button" onClick={() => void connectTeams()} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover">Connect</button>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-foreground">Discord</h2>
          </div>
          <p className="mt-1 text-xs text-foreground-muted">{discord.loading ? "Checking…" : discord.config.connected ? "Connected" : "Not connected"}</p>
          {discord.config.connected ? (
            <button type="button" onClick={() => void disconnect("discord")} className="mt-2 text-xs font-medium text-danger hover:underline">Disconnect</button>
          ) : (
            <div className="mt-2 flex flex-col gap-2">
              <input value={discordGuildId} onChange={(e) => setDiscordGuildId(e.target.value)} placeholder="Server (guild) ID" className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs outline-none focus:border-accent" />
              <input value={discordBotToken} onChange={(e) => setDiscordBotToken(e.target.value)} placeholder="Bot token" type="password" className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs outline-none focus:border-accent" />
              <button type="button" onClick={() => void connectDiscord()} className="self-start rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover">Connect</button>
            </div>
          )}
        </div>

        <UniversalIntegrationsSection orgId={org?.id} onError={setError} />
      </div>
    </div>
  );
}

function UniversalIntegrationsSection({ orgId, onError }: { orgId: string | undefined; onError: (e: string) => void }) {
  const [connections, setConnections] = useState<UniversalConnection[]>([]);
  const [newName, setNewName] = useState("");
  const [newProvider, setNewProvider] = useState("webhook");
  const [newAction, setNewAction] = useState("log_only");
  const [justCreatedToken, setJustCreatedToken] = useState<{ id: string; token: string } | null>(null);

  const load = useCallback(async () => {
    if (!orgId) return;
    try {
      setConnections(await api.get<UniversalConnection[]>(`/organizations/${orgId}/integrations/connections`));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to load integration connections");
    }
  }, [orgId, onError]);

  useEffect(() => {
    void load();
  }, [load]);

  async function createConnection() {
    if (!orgId || !newName.trim()) return;
    try {
      const created = await api.post<UniversalConnection>(`/organizations/${orgId}/integrations/connections`, { name: newName, provider: newProvider, action: newAction });
      setJustCreatedToken({ id: created.id, token: created.token! });
      setNewName("");
      await load();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to create connection");
    }
  }

  async function deleteConnection(id: string) {
    if (!orgId) return;
    await api.delete(`/organizations/${orgId}/integrations/connections/${id}`);
    if (justCreatedToken?.id === id) setJustCreatedToken(null);
    await load();
  }

  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <h2 className="text-sm font-semibold text-foreground">Zapier / Make / n8n / custom webhooks</h2>
      <p className="mt-1 text-xs text-foreground-muted">
        Create a connection below, then point your Zapier action, Make scenario, n8n workflow, or any CRM's outgoing
        webhook at the URL shown — with the token as a Bearer header.
      </p>

      {justCreatedToken && (
        <div className="mt-3 rounded-lg border border-accent bg-accent-soft/40 p-3 text-xs">
          <p className="font-medium text-foreground">Save this token now — it won't be shown again.</p>
          <p className="mt-1 break-all font-mono text-foreground-muted">{base}/integrations/inbound/{justCreatedToken.id}</p>
          <p className="mt-1 break-all font-mono text-foreground-muted">Authorization: Bearer {justCreatedToken.token}</p>
        </div>
      )}

      <div className="mt-3 flex flex-col gap-2">
        {connections.map((c) => (
          <div key={c.id} className="flex items-center justify-between rounded-lg border border-border bg-background p-3 text-sm">
            <span>{c.name} — {c.provider} → {c.action}</span>
            <button type="button" onClick={() => void deleteConnection(c.id)} className="text-xs font-medium text-danger hover:underline">Delete</button>
          </div>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Connection name" className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs outline-none focus:border-accent" />
        <select value={newProvider} onChange={(e) => setNewProvider(e.target.value)} className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs">
          <option value="webhook">Generic webhook</option>
          <option value="zapier">Zapier</option>
          <option value="make">Make</option>
          <option value="n8n">n8n</option>
        </select>
        <select value={newAction} onChange={(e) => setNewAction(e.target.value)} className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs">
          <option value="log_only">Log only</option>
          <option value="ingest_document">Ingest as a document</option>
        </select>
        <button type="button" onClick={() => void createConnection()} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover">Create</button>
      </div>
    </div>
  );
}
