"use client";

interface ABTestVariantSelectorProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function ABTestVariantSelector({ label, value, onChange, placeholder }: ABTestVariantSelectorProps) {
  return (
    <div>
      <label className="block text-xs font-medium uppercase text-foreground-muted">{label}</label>
      <textarea
        value={value} onChange={(e) => onChange(e.target.value)} rows={4} placeholder={placeholder}
        className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 font-mono text-xs text-foreground"
      />
    </div>
  );
}
