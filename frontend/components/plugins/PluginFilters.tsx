"use client";

import type { PluginCategory, PluginPricing } from "@/lib/types";

const CATEGORIES: PluginCategory[] = ["analytics", "automation", "communication", "data", "integration", "productivity", "security", "other"];
const PRICING_OPTIONS: PluginPricing[] = ["free", "paid", "freemium"];

interface PluginFiltersProps {
  category: string;
  onCategoryChange: (category: string) => void;
  pricing: string;
  onPricingChange: (pricing: string) => void;
  sortBy: string;
  onSortByChange: (sortBy: string) => void;
  minRating: number | undefined;
  onMinRatingChange: (rating: number | undefined) => void;
}

// Partie 16 (ter) -- category/pricing/sort/min-rating filters for the
// marketplace listing. `pricing` filters by the real, declared
// free/paid/freemium value -- see Plugin.pricing's own model comment
// for the honest scope (declared metadata, not an enforced purchase:
// no real checkout flow exists behind `paid`/`freemium` in this pass).
export default function PluginFilters({ category, onCategoryChange, pricing, onPricingChange, sortBy, onSortByChange, minRating, onMinRatingChange }: PluginFiltersProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <select value={category} onChange={(e) => onCategoryChange(e.target.value)} className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs">
        <option value="">All categories</option>
        {CATEGORIES.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>
      <select value={pricing} onChange={(e) => onPricingChange(e.target.value)} className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs">
        <option value="">Any price</option>
        {PRICING_OPTIONS.map((p) => (
          <option key={p} value={p}>{p}</option>
        ))}
      </select>
      <select value={sortBy} onChange={(e) => onSortByChange(e.target.value)} className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs">
        <option value="date">Newest</option>
        <option value="popularity">Most popular</option>
        <option value="rating">Highest rated</option>
        <option value="price">Price: low to high</option>
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
