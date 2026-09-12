"use client";

const MAX_LENGTH = 20_000;

interface CustomCSSEditorProps {
  value: string;
  onChange: (value: string) => void;
}

export function CustomCSSEditor({ value, onChange }: CustomCSSEditorProps) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium uppercase text-foreground-muted">Custom CSS</label>
        <span className="text-xs text-foreground-muted">{value.length}/{MAX_LENGTH}</span>
      </div>
      <textarea
        value={value} onChange={(e) => onChange(e.target.value)} maxLength={MAX_LENGTH} rows={8} spellCheck={false}
        placeholder=".my-brand-header { background: linear-gradient(...); }"
        className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 font-mono text-xs text-foreground"
      />
      <p className="mt-1 text-xs text-foreground-muted">Applied on your organization's own branded pages only.</p>
    </div>
  );
}
