"use client";

import { useState } from "react";
import { usePlugins } from "@/lib/hooks/usePlugins";
import PluginDetail from "./PluginDetail";
import PluginFilters from "./PluginFilters";
import PluginInstallButton from "./PluginInstallButton";
import PluginList from "./PluginList";
import PluginSearch from "./PluginSearch";

interface PluginMarketplaceProps {
  orgId: string;
  currentUserId?: string;
  onError?: (message: string) => void;
}

// Partie 16 (ter) -- the real "Browse" experience: search, filter,
// sort, select a plugin for its full PluginDetail, install directly
// from the list.
export default function PluginMarketplace({ orgId, currentUserId, onError }: PluginMarketplaceProps) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [pricing, setPricing] = useState("");
  const [sortBy, setSortBy] = useState("date");
  const [minRating, setMinRating] = useState<number | undefined>(undefined);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { plugins, loading, reload } = usePlugins({ search, category, pricing, sort_by: sortBy as "date" | "popularity" | "rating" | "price", min_rating: minRating });

  if (selectedId) {
    return (
      <div className="flex flex-col gap-3">
        <button type="button" onClick={() => setSelectedId(null)} className="self-start text-xs font-medium text-accent-hover hover:underline">
          &larr; Back to marketplace
        </button>
        <PluginDetail orgId={orgId} pluginId={selectedId} currentUserId={currentUserId} onError={onError} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <PluginSearch value={search} onChange={setSearch} />
        <PluginFilters category={category} onCategoryChange={setCategory} pricing={pricing} onPricingChange={setPricing} sortBy={sortBy} onSortByChange={setSortBy} minRating={minRating} onMinRatingChange={setMinRating} />
      </div>

      {loading ? (
        <p className="text-sm text-foreground-muted">Loading…</p>
      ) : (
        <PluginList
          plugins={plugins}
          onSelect={(plugin) => setSelectedId(plugin.id)}
          renderActions={(plugin) => <PluginInstallButton orgId={orgId} pluginId={plugin.id} onInstalled={reload} onError={onError} />}
        />
      )}
    </div>
  );
}
