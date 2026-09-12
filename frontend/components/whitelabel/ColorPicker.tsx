"use client";

interface ColorPickerProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

const HEX_PATTERN = /^#[0-9a-fA-F]{6}$/;

export function ColorPicker({ label, value, onChange }: ColorPickerProps) {
  const isValid = HEX_PATTERN.test(value);

  return (
    <div>
      <label className="block text-xs font-medium uppercase text-foreground-muted">{label}</label>
      <div className="mt-1 flex items-center gap-2">
        <input
          type="color" value={isValid ? value : "#000000"}
          onChange={(e) => onChange(e.target.value)}
          className="h-9 w-9 shrink-0 cursor-pointer rounded border border-border bg-transparent p-0.5"
        />
        <input
          type="text" value={value} onChange={(e) => onChange(e.target.value)}
          placeholder="#2563eb"
          className={`w-28 rounded-lg border px-2 py-1.5 text-sm text-foreground ${isValid ? "border-border" : "border-danger"}`}
        />
      </div>
      {!isValid && <p className="mt-1 text-xs text-danger">Must be a hex color, e.g. #2563eb</p>}
    </div>
  );
}
