"use client";

import LoadingState from "@/components/LoadingState";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { deletePlugin, listPublishedPlugins } from "@/lib/services/plugins";
import type { Plugin } from "@/lib/types";
import InstalledPlugins from "@/components/plugins/InstalledPlugins";
import PluginCreateForm from "@/components/plugins/PluginCreateForm";
import PluginMarketplace from "@/components/plugins/PluginMarketplace";
import PluginVersionForm from "@/components/plugins/PluginVersionForm";

const TABS = ["Browse", "My plugins", "Installed"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABELS: Record<Tab, string> = { Browse: "Parcourir", "My plugins": "Mes plugins", Installed: "Installés" };

// Partie 16 (ter) -- one consolidated page composing the real,
// separate plugin components (PluginMarketplace/InstalledPlugins/
// PluginCreateForm/PluginVersionForm) -- same tabbed-single-page
// discipline as every other multi-section screen in this project
// (e.g. /dashboard/billing), not a separate route per concern.
export default function MarketplacePage() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("Browse");
  const [error, setError] = useState<string | null>(null);

  if (orgLoading || !org) {
    return <LoadingState fullScreen={false} />;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold text-foreground">Marketplace</h1>
      <p className="mt-1 text-sm text-foreground-muted">Parcourez, publiez et gérez les plugins pour {org.name}.</p>

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
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === "Browse" && <PluginMarketplace orgId={org.id} currentUserId={user?.id} onError={setError} />}
        {tab === "My plugins" && <MyPluginsTab orgId={org.id} onError={setError} />}
        {tab === "Installed" && <InstalledPlugins orgId={org.id} onError={setError} />}
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

function MyPluginsTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [published, setPublished] = useState<Plugin[]>([]);
  const [managingId, setManagingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPublished(await listPublishedPlugins(orgId));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec du chargement de vos plugins");
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function remove(pluginId: string) {
    try {
      await deletePlugin(orgId, pluginId);
      await load();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec de la suppression de ce plugin");
    }
  }

  const managedPlugin = published.find((p) => p.id === managingId) ?? null;

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
                  <p className="mt-1 text-xs text-danger">Rejeté : {plugin.rejection_reason}</p>
                )}
              </div>
              <div className="flex gap-3">
                <button type="button" onClick={() => setManagingId(managingId === plugin.id ? null : plugin.id)} className="text-xs font-medium text-accent-hover hover:underline">
                  Nouvelle version
                </button>
                <button type="button" onClick={() => void remove(plugin.id)} className="text-xs font-medium text-danger hover:underline">Supprimer</button>
              </div>
            </div>
            {managingId === plugin.id && managedPlugin && (
              <div className="mt-3">
                <PluginVersionForm
                  orgId={orgId}
                  plugin={managedPlugin}
                  onPublished={() => {
                    setManagingId(null);
                    void load();
                  }}
                  onError={onError}
                />
              </div>
            )}
          </div>
        ))}
        {published.length === 0 && <p className="text-sm text-foreground-muted">Vous n&apos;avez pas encore publié de plugin.</p>}
      </div>

      <PluginCreateForm orgId={orgId} onPublished={() => void load()} onError={onError} />
    </div>
  );
}
