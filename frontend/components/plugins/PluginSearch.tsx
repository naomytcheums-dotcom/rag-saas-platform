"use client";

interface PluginSearchProps {
  value: string;
  onChange: (value: string) => void;
}

// Partie 16 (ter) -- plain search input, controlled by the parent.
export default function PluginSearch({ value, onChange }: PluginSearchProps) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Search plugins…"
      className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-accent"
    />
  );
}
