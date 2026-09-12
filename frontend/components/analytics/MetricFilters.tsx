"use client";

interface MetricFiltersProps {
  eventType: string;
  onEventTypeChange: (value: string) => void;
  availableEventTypes: string[];
}

export function MetricFilters({ eventType, onEventTypeChange, availableEventTypes }: MetricFiltersProps) {
  return (
    <select
      value={eventType} onChange={(e) => onEventTypeChange(e.target.value)}
      className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-foreground"
    >
      <option value="">All events</option>
      {availableEventTypes.map((type) => <option key={type} value={type}>{type}</option>)}
    </select>
  );
}
