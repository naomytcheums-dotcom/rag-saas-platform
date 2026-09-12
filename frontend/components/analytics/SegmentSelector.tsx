"use client";

// Real, honest scope: this app's analytics data (AnalyticsEvent) isn't
// segmented by any dimension beyond organization/user today (no plan
// tier, no role, no geography tracked on the event itself) -- so "All
// users" is the only real, working segment. The selector exists so a
// future real segment axis (e.g. by Subscription.plan_id) has an
// obvious place to plug in, without a fabricated breakdown in the
// meantime.

interface SegmentSelectorProps {
  value: string;
  onChange: (value: string) => void;
}

export function SegmentSelector({ value, onChange }: SegmentSelectorProps) {
  return (
    <select
      value={value} onChange={(e) => onChange(e.target.value)}
      className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-foreground"
    >
      <option value="all">All users</option>
    </select>
  );
}
