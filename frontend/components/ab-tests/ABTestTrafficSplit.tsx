"use client";

interface ABTestTrafficSplitProps {
  value: number;
  onChange: (value: number) => void;
}

export function ABTestTrafficSplit({ value, onChange }: ABTestTrafficSplitProps) {
  return (
    <div>
      <label htmlFor="ab-traffic-split" className="block text-xs font-medium uppercase text-foreground-muted">Traffic split</label>
      <div className="mt-1 flex items-center gap-3">
        <input
          id="ab-traffic-split" type="range" min={0} max={100} value={value}
          onChange={(e) => onChange(Number(e.target.value))} className="flex-1"
        />
        <span className="w-24 text-sm text-foreground">{value}% A / {100 - value}% B</span>
      </div>
    </div>
  );
}
