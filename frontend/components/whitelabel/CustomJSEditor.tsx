"use client";

const MAX_LENGTH = 20_000;

interface CustomJSEditorProps {
  value: string;
  onChange: (value: string) => void;
}

export function CustomJSEditor({ value, onChange }: CustomJSEditorProps) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium uppercase text-foreground-muted">Custom JavaScript</label>
        <span className="text-xs text-foreground-muted">{value.length}/{MAX_LENGTH}</span>
      </div>
      <textarea
        value={value} onChange={(e) => onChange(e.target.value)} maxLength={MAX_LENGTH} rows={8} spellCheck={false}
        placeholder="// runs on your organization's own branded pages"
        className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 font-mono text-xs text-foreground"
      />
      <p className="mt-1 text-xs rounded-lg bg-warning-soft px-2 py-1 text-warning">
        This script runs as-is with no sanitization -- only add code you trust, the same way you would any third-party widget embed.
      </p>
    </div>
  );
}
