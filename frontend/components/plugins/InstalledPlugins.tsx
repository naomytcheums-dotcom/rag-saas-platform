"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { useInstalledPlugins } from "@/lib/hooks/useInstalledPlugins";
import { disablePlugin, enablePlugin, uninstallPlugin } from "@/lib/services/plugins";
import PluginConfigForm from "./PluginConfigForm";

interface InstalledPluginsProps {
  orgId: string;
  onError?: (message: string) => void;
}

// Partie 16 (ter) -- this org's installed plugins: enable/disable,
// per-installation config, uninstall.
export default function InstalledPlugins({ orgId, onError }: InstalledPluginsProps) {
  const { installations, loading, reload } = useInstalledPlugins(orgId);
  const [expanded, setExpanded] = useState<string | null>(null);

  async function toggle(installationId: string, enabled: boolean) {
    try {
      await (enabled ? disablePlugin : enablePlugin)(orgId, installationId);
      await reload();
    } catch (err) {
      onError?.(err instanceof ApiError ? String(err.detail) : "Failed to update this installation");
    }
  }

  async function remove(installationId: string) {
    try {
      await uninstallPlugin(orgId, installationId);
      await reload();
    } catch (err) {
      onError?.(err instanceof ApiError ? String(err.detail) : "Failed to uninstall this plugin");
    }
  }

  if (loading) return <p className="text-sm text-foreground-muted">Loading…</p>;
  if (installations.length === 0) return <p className="text-sm text-foreground-muted">No plugins installed yet.</p>;

  return (
    <div className="flex flex-col gap-2">
      {installations.map((installation) => (
        <div key={installation.id} className="rounded-xl border border-border bg-surface p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-foreground">Plugin {installation.plugin_id.slice(0, 8)}</p>
              <p className="text-xs text-foreground-muted">
                {installation.enabled ? "Enabled" : "Disabled"} — installed {new Date(installation.installed_at).toLocaleDateString()}
              </p>
            </div>
            <div className="flex gap-3">
              <button type="button" onClick={() => setExpanded(expanded === installation.id ? null : installation.id)} className="text-xs font-medium text-accent-hover hover:underline">
                Configure
              </button>
              <button type="button" onClick={() => void toggle(installation.id, installation.enabled)} className="text-xs font-medium text-accent-hover hover:underline">
                {installation.enabled ? "Disable" : "Enable"}
              </button>
              <button type="button" onClick={() => void remove(installation.id)} className="text-xs font-medium text-danger hover:underline">Uninstall</button>
            </div>
          </div>
          {expanded === installation.id && (
            <div className="mt-3">
              <PluginConfigForm orgId={orgId} installation={installation} onSaved={reload} onError={onError} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
