"use client";

import type { Plugin } from "@/lib/types";
import PluginCard from "./PluginCard";

interface PluginListProps {
  plugins: Plugin[];
  onSelect?: (plugin: Plugin) => void;
  renderActions?: (plugin: Plugin) => React.ReactNode;
  emptyMessage?: string;
}

// Partie 16 (ter) -- a plain list of PluginCard, no fetching of its
// own (the caller, e.g. PluginMarketplace, owns the data).
export default function PluginList({ plugins, onSelect, renderActions, emptyMessage = "No plugins found." }: PluginListProps) {
  if (plugins.length === 0) {
    return <p className="text-sm text-foreground-muted">{emptyMessage}</p>;
  }
  return (
    <div className="flex flex-col gap-2">
      {plugins.map((plugin) => (
        <PluginCard key={plugin.id} plugin={plugin} onSelect={onSelect} actions={renderActions?.(plugin)} />
      ))}
    </div>
  );
}
