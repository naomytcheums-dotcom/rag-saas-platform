"use client";

const STATUSES = ["all", "draft", "running", "paused", "completed"];

interface ABTestFiltersProps {
  status: string;
  onStatusChange: (value: string) => void;
}

export function ABTestFilters({ status, onStatusChange }: ABTestFiltersProps) {
  return (
    <select
      value={status} onChange={(e) => onStatusChange(e.target.value)}
      className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-foreground"
    >
      {STATUSES.map((s) => <option key={s} value={s}>{s === "all" ? "All statuses" : s}</option>)}
    </select>
  );
}
