"use client";

import type { Plugin } from "@/lib/types";

interface PluginCardProps {
  plugin: Plugin;
  onSelect?: (plugin: Plugin) => void;
  actions?: React.ReactNode;
}

// Partie 16 (ter) -- one plugin, presentational.
export default function PluginCard({ plugin, onSelect, actions }: PluginCardProps) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <button type="button" onClick={() => onSelect?.(plugin)} className="text-left">
          <h3 className="text-sm font-semibold text-foreground hover:text-accent-hover">
            {plugin.name} <span className="ml-1 rounded-full bg-accent-soft/40 px-2 py-0.5 text-xs font-medium text-accent-hover">{plugin.pricing === "free" ? "Free" : plugin.pricing === "paid" ? `${plugin.price} EUR` : `Freemium — from ${plugin.price} EUR`}</span>
          </h3>
          <p className="mt-0.5 text-xs text-foreground-muted">v{plugin.version} &middot; {plugin.category}</p>
          <p className="mt-1 text-xs text-foreground-muted">{plugin.description}</p>
          <p className="mt-1 text-xs text-foreground-muted">{plugin.install_count} install{plugin.install_count === 1 ? "" : "s"}</p>
        </button>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
