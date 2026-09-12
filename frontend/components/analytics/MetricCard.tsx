"use client";

interface MetricCardProps {
  label: string;
  value: string | number | null;
  suffix?: string;
  hint?: string;
}

export function MetricCard({ label, value, suffix, hint }: MetricCardProps) {
  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h2 className="text-xs font-medium uppercase text-foreground-muted">{label}</h2>
      <p className="mt-2 text-2xl font-semibold text-foreground">
        {value === null || value === undefined ? "—" : value}{value !== null && suffix ? suffix : ""}
      </p>
      {hint && <p className="mt-1 text-xs text-foreground-muted">{hint}</p>}
    </div>
  );
}
