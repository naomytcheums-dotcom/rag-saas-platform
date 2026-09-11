"use client";

import type { PluginCategory } from "@/lib/types";

const CATEGORIES: PluginCategory[] = ["analytics", "automation", "communication", "data", "integration", "productivity", "security", "other"];

interface PluginFiltersProps {
  category: string;
  onCategoryChange: (category: string) => void;
  sortBy: string;
  onSortByChange: (sortBy: string) => void;
  minRating: number | undefined;
  onMinRatingChange: (rating: number | undefined) => void;
}

// Partie 16 (ter) -- category/sort/min-rating filters for the
// marketplace listing. No free/paid filter -- there is no real pricing
// model for plugins in this pass (see api/services/plugins.py's own
// docstring on list_marketplace_plugins).
export default function PluginFilters({ category, onCategoryChange, sortBy, onSortByChange, minRating, onMinRatingChange }: PluginFiltersProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <select value={category} onChange={(e) => onCategoryChange(e.target.value)} className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs">
        <option value="">All categories</option>
        {CATEGORIES.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>
      <select value={sortBy} onChange={(e) => onSortByChange(e.target.value)} className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs">
        <option value="date">Newest</option>
        <option value="popularity">Most popular</option>
        <option value="rating">Highest rated</option>
      </select>
      <select
        value={minRating ?? ""}
        onChange={(e) => onMinRatingChange(e.target.value ? Number(e.target.value) : undefined)}
        className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs"
      >
        <option value="">Any rating</option>
        {[4, 3, 2, 1].map((n) => (
          <option key={n} value={n}>{n}+ stars</option>
        ))}
      </select>
    </div>
  );
}
