"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import type { Plugin, PluginInstallation, PluginPermission, PluginRatingSummary, PluginReview } from "@/lib/types";

const TABS = ["Browse", "My plugins", "Installed"] as const;
type Tab = (typeof TABS)[number];

export default function MarketplacePage() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const [tab, setTab] = useState<Tab>("Browse");
  const [error, setError] = useState<string | null>(null);

  if (orgLoading || !org) {
    return <div className="mx-auto max-w-4xl text-sm text-foreground-muted">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold text-foreground">Marketplace</h1>
      <p className="mt-1 text-sm text-foreground-muted">Browse, publish, and manage plugins for {org.name}.</p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      <div className="mt-5 flex flex-wrap gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm font-medium transition-colors ${
              tab === t ? "border-b-2 border-accent text-accent-hover" : "text-foreground-muted hover:text-foreground"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === "Browse" && <BrowseTab orgId={org.id} onError={setError} />}
        {tab === "My plugins" && <MyPluginsTab orgId={org.id} onError={setError} />}
        {tab === "Installed" && <InstalledTab orgId={org.id} onError={setError} />}
      </div>
    </div>
  );
}

function statusBadge(status: Plugin["status"]) {
  const classes: Record<Plugin["status"], string> = {
    pending: "bg-accent-soft/40 text-accent-hover",
    approved: "bg-success-soft text-success",
    rejected: "bg-danger-soft text-danger",
    suspended: "bg-danger-soft text-danger",
  };
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${classes[status]}`}>{status}</span>;
}

// -------------------------------------------------------------- Browse

function BrowseTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPlugins(await api.get<Plugin[]>(`/marketplace/plugins${search ? `?search=${encodeURIComponent(search)}` : ""}`));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to load the marketplace");
    }
  }, [search, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function install(pluginId: string) {
    try {
      await api.post(`/organizations/${orgId}/plugins/${pluginId}/install`);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to install this plugin");
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search plugins…"
        className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-accent"
      />

      <div className="flex flex-col gap-2">
        {plugins.map((plugin) => (
          <div key={plugin.id} className="rounded-xl border border-border bg-surface p-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-foreground">{plugin.name}</h3>
                <p className="mt-0.5 text-xs text-foreground-muted">v{plugin.version} — {plugin.description}</p>
              </div>
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => setExpanded(expanded === plugin.id ? null : plugin.id)} className="text-xs font-medium text-accent-hover hover:underline">
                  Reviews
                </button>
                <button type="button" onClick={() => void install(plugin.id)} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover">
                  Install
                </button>
              </div>
            </div>
            {expanded === plugin.id && <PluginReviews pluginId={plugin.id} orgId={orgId} onError={onError} />}
          </div>
        ))}
        {plugins.length === 0 && <p className="text-sm text-foreground-muted">No plugins found.</p>}
      </div>
    </div>
  );
}

function PluginReviews({ pluginId, orgId, onError }: { pluginId: string; orgId: string; onError: (e: string) => void }) {
  const [summary, setSummary] = useState<PluginRatingSummary | null>(null);
  const [reviews, setReviews] = useState<PluginReview[]>([]);
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");

  const load = useCallback(async () => {
    try {
      setSummary(await api.get<PluginRatingSummary>(`/marketplace/plugins/${pluginId}/rating`));
      setReviews(await api.get<PluginReview[]>(`/marketplace/plugins/${pluginId}/reviews`));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to load reviews");
    }
  }, [pluginId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function submit() {
    try {
      await api.post(`/organizations/${orgId}/plugins/${pluginId}/reviews`, { rating, comment: comment || null });
      setComment("");
      await load();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to submit review");
    }
  }

  return (
    <div className="mt-3 rounded-lg border border-border bg-background p-3 text-xs">
      <p className="font-medium text-foreground">
        {summary?.average_rating != null ? `${summary.average_rating} / 5` : "No ratings yet"} ({summary?.review_count ?? 0} review{summary?.review_count === 1 ? "" : "s"})
      </p>
      <div className="mt-2 flex flex-col gap-1">
        {reviews.map((r) => (
          <p key={r.id} className="text-foreground-muted">{r.rating}/5 — {r.comment ?? "(no comment)"}</p>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <select value={rating} onChange={(e) => setRating(Number(e.target.value))} className="rounded-lg border border-border bg-surface px-2.5 py-1 text-xs">
          {[5, 4, 3, 2, 1].map((n) => (
            <option key={n} value={n}>{n} / 5</option>
          ))}
        </select>
        <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Comment (optional)" className="flex-1 rounded-lg border border-border bg-surface px-2.5 py-1 text-xs outline-none focus:border-accent" />
        <button type="button" onClick={() => void submit()} className="rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-white hover:bg-accent-hover">Rate</button>
      </div>
    </div>
  );
}

// -------------------------------------------------------------- My plugins (publish)

function MyPluginsTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [published, setPublished] = useState<Plugin[]>([]);
  const [permissions, setPermissions] = useState<PluginPermission[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [version, setVersion] = useState("1.0.0");
  const [entryPoint, setEntryPoint] = useState("index.js");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [codeText, setCodeText] = useState("// your plugin code here\n");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    try {
      setPublished(await api.get<Plugin[]>(`/organizations/${orgId}/plugins/published`));
      setPermissions(await api.get<PluginPermission[]>("/marketplace/permissions"));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to load your plugins");
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  function togglePermission(id: string) {
    setSelectedPermissions((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]));
  }

  async function publish() {
    if (!name.trim() || !description.trim()) return;
    setSubmitting(true);
    try {
      const manifest = { name, version, entry_point: entryPoint, description, permissions: selectedPermissions };
      const manifestBlob = new Blob([JSON.stringify(manifest)], { type: "application/json" });
      const codeBlob = new Blob([codeText], { type: "text/plain" });
      await api.postMultipart(`/organizations/${orgId}/plugins/publish`, { name, description }, { manifest: manifestBlob, code: codeBlob });
      setName("");
      setDescription("");
      await load();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to publish plugin");
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(pluginId: string) {
    await api.delete(`/organizations/${orgId}/plugins/${pluginId}`);
    await load();
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        {published.map((plugin) => (
          <div key={plugin.id} className="rounded-xl border border-border bg-surface p-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-foreground">{plugin.name} <span className="ml-1">{statusBadge(plugin.status)}</span></h3>
                <p className="mt-0.5 text-xs text-foreground-muted">v{plugin.version} — {plugin.description}</p>
                {plugin.status === "rejected" && plugin.rejection_reason && (
                  <p className="mt-1 text-xs text-danger">Rejected: {plugin.rejection_reason}</p>
                )}
              </div>
              <button type="button" onClick={() => void remove(plugin.id)} className="text-xs font-medium text-danger hover:underline">Delete</button>
            </div>
          </div>
        ))}
        {published.length === 0 && <p className="text-sm text-foreground-muted">You haven&apos;t published any plugins yet.</p>}
      </div>

      <div className="rounded-xl border border-border bg-surface p-4">
        <h3 className="text-sm font-semibold text-foreground">Publish a new plugin</h3>
        <p className="mt-1 text-xs text-foreground-muted">Reviewed by an admin before it appears in the marketplace.</p>

        <div className="mt-3 flex flex-col gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Plugin name" className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-accent" />
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description" rows={2} className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-accent" />
          <div className="flex gap-2">
            <input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="Version (e.g. 1.0.0)" className="w-1/2 rounded-lg border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-accent" />
            <select value={entryPoint} onChange={(e) => setEntryPoint(e.target.value)} className="w-1/2 rounded-lg border border-border bg-background px-3 py-1.5 text-sm">
              <option value="index.js">index.js</option>
              <option value="index.py">index.py</option>
            </select>
          </div>

          <div>
            <p className="text-xs font-medium text-foreground-muted">Permissions</p>
            <div className="mt-1 flex flex-wrap gap-2">
              {permissions.map((p) => (
                <label key={p.id} className="flex items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1 text-xs">
                  <input type="checkbox" checked={selectedPermissions.includes(p.id)} onChange={() => togglePermission(p.id)} />
                  {p.label}
                </label>
              ))}
            </div>
          </div>

          <textarea
            value={codeText}
            onChange={(e) => setCodeText(e.target.value)}
            rows={6}
            className="rounded-lg border border-border bg-background px-3 py-1.5 font-mono text-xs outline-none focus:border-accent"
          />

          <button
            type="button"
            disabled={submitting || !name.trim() || !description.trim()}
            onClick={() => void publish()}
            className="self-start rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {submitting ? "Publishing…" : "Publish"}
          </button>
        </div>
      </div>
    </div>
  );
}

// -------------------------------------------------------------- Installed

function InstalledTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [installations, setInstallations] = useState<PluginInstallation[]>([]);

  const load = useCallback(async () => {
    try {
      setInstallations(await api.get<PluginInstallation[]>(`/organizations/${orgId}/plugins/installed`));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to load installed plugins");
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function toggle(installation: PluginInstallation) {
    await api.patch(`/organizations/${orgId}/plugins/installed/${installation.id}`, { enabled: !installation.enabled });
    await load();
  }

  async function uninstall(installationId: string) {
    await api.delete(`/organizations/${orgId}/plugins/installed/${installationId}`);
    await load();
  }

  return (
    <div className="flex flex-col gap-2">
      {installations.map((installation) => (
        <div key={installation.id} className="flex items-center justify-between rounded-xl border border-border bg-surface p-4">
          <div>
            <p className="text-sm text-foreground">Plugin {installation.plugin_id.slice(0, 8)}</p>
            <p className="text-xs text-foreground-muted">{installation.enabled ? "Enabled" : "Disabled"} — installed {new Date(installation.installed_at).toLocaleDateString()}</p>
          </div>
          <div className="flex gap-3">
            <button type="button" onClick={() => void toggle(installation)} className="text-xs font-medium text-accent-hover hover:underline">
              {installation.enabled ? "Disable" : "Enable"}
            </button>
            <button type="button" onClick={() => void uninstall(installation.id)} className="text-xs font-medium text-danger hover:underline">Uninstall</button>
          </div>
        </div>
      ))}
      {installations.length === 0 && <p className="text-sm text-foreground-muted">No plugins installed yet.</p>}
    </div>
  );
}
