"use client";

interface ABTestVariantSelectorProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function ABTestVariantSelector({ label, value, onChange, placeholder }: ABTestVariantSelectorProps) {
  const id = `ab-variant-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-medium uppercase text-foreground-muted">{label}</label>
      <textarea
        id={id}
        value={value} onChange={(e) => onChange(e.target.value)} rows={4} placeholder={placeholder}
        className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 font-mono text-xs text-foreground"
      />
    </div>
  );
}
