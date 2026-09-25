"use client";

import LoadingState from "@/components/LoadingState";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";
import { deletePlugin, listPublishedPlugins } from "@/lib/services/plugins";
import type { Plugin } from "@/lib/types";
import InstalledPlugins from "@/components/plugins/InstalledPlugins";
import PluginCreateForm from "@/components/plugins/PluginCreateForm";
import PluginMarketplace from "@/components/plugins/PluginMarketplace";
import PluginVersionForm from "@/components/plugins/PluginVersionForm";

const TABS = ["Browse", "My plugins", "Installed"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABEL_KEYS: Record<Tab, string> = {
  Browse: "marketplace.tab_browse",
  "My plugins": "marketplace.tab_my_plugins",
  Installed: "marketplace.tab_installed",
};

// Partie 16 (ter) -- one consolidated page composing the real,
// separate plugin components (PluginMarketplace/InstalledPlugins/
// PluginCreateForm/PluginVersionForm) -- same tabbed-single-page
// discipline as every other multi-section screen in this project
// (e.g. /dashboard/billing), not a separate route per concern.
export default function MarketplacePage() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const { user } = useAuth();
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("Browse");
  const [error, setError] = useState<string | null>(null);

  if (orgLoading || !org) {
    return <LoadingState fullScreen={false} />;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold text-foreground">{t("marketplace.title")}</h1>
      <p className="mt-1 text-sm text-foreground-muted">{t("marketplace.subtitle")} {org.name}.</p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      <div className="mt-5 flex flex-wrap gap-1 border-b border-border">
        {TABS.map((tabKey) => (
          <button
            key={tabKey}
            type="button"
            onClick={() => setTab(tabKey)}
            className={`px-3 py-2 text-sm font-medium transition-colors ${
              tab === tabKey ? "border-b-2 border-accent text-accent-hover" : "text-foreground-muted hover:text-foreground"
            }`}
          >
            {t(TAB_LABEL_KEYS[tabKey])}
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

function statusBadge(status: Plugin["status"], t: (key: string) => string) {
  const classes: Record<Plugin["status"], string> = {
    pending: "bg-accent-soft/40 text-accent-hover",
    approved: "bg-success-soft text-success",
    rejected: "bg-danger-soft text-danger",
    suspended: "bg-danger-soft text-danger",
  };
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${classes[status]}`}>{t(`marketplace.status_${status}`)}</span>;
}

function MyPluginsTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const { t } = useTranslation();
  const [published, setPublished] = useState<Plugin[]>([]);
  const [managingId, setManagingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPublished(await listPublishedPlugins(orgId));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("marketplace.error_plugins_load"));
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
      onError(err instanceof ApiError ? String(err.detail) : t("marketplace.error_plugin_delete"));
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
                <h3 className="text-sm font-semibold text-foreground">{plugin.name} <span className="ml-1">{statusBadge(plugin.status, t)}</span></h3>
                <p className="mt-0.5 text-xs text-foreground-muted">v{plugin.version} — {plugin.description}</p>
                {plugin.status === "rejected" && plugin.rejection_reason && (
                  <p className="mt-1 text-xs text-danger">{t("marketplace.rejected")} {plugin.rejection_reason}</p>
                )}
              </div>
              <div className="flex gap-3">
                <button type="button" onClick={() => setManagingId(managingId === plugin.id ? null : plugin.id)} className="text-xs font-medium text-accent-hover hover:underline">
                  Nouvelle version
                </button>
                <button type="button" onClick={() => void remove(plugin.id)} className="text-xs font-medium text-danger hover:underline">{t("marketplace.delete")}</button>
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
        {published.length === 0 && <p className="text-sm text-foreground-muted">{t("marketplace.empty")}</p>}
      </div>

      <PluginCreateForm orgId={orgId} onPublished={() => void load()} onError={onError} />
    </div>
  );
}
