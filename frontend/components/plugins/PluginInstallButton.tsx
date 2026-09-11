"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { installPlugin } from "@/lib/services/plugins";

interface PluginInstallButtonProps {
  orgId: string;
  pluginId: string;
  onInstalled?: () => void;
  onError?: (message: string) => void;
}

// Partie 16 (ter) -- POST /organizations/{org_id}/plugins/{id}/install.
export default function PluginInstallButton({ orgId, pluginId, onInstalled, onError }: PluginInstallButtonProps) {
  const [installing, setInstalling] = useState(false);

  async function install() {
    setInstalling(true);
    try {
      await installPlugin(orgId, pluginId);
      onInstalled?.();
    } catch (err) {
      const message = err instanceof ApiError ? String(err.detail) : "Failed to install this plugin";
      onError?.(message);
    } finally {
      setInstalling(false);
    }
  }

  return (
    <button
      type="button"
      disabled={installing}
      onClick={() => void install()}
      className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
    >
      {installing ? "Installing…" : "Install"}
    </button>
  );
}
