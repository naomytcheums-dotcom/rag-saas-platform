"use client";

interface Provider {
  id: string;
  name: string;
  description: string;
}

interface ProviderCardProps {
  provider: Provider;
  selected: boolean;
  onSelect: (id: string) => void;
}

// Partie 15.1 -- one real provider from GET /integrations/providers
// (api/services/integrations.py's own INTEGRATION_PROVIDERS catalog).
export default function ProviderCard({ provider, selected, onSelect }: ProviderCardProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(provider.id)}
      className={`rounded-lg border px-3 py-2 text-left text-xs transition ${
        selected ? "border-accent bg-accent-soft/40" : "border-border bg-background hover:border-accent"
      }`}
    >
      <p className="font-medium text-foreground">{provider.name}</p>
      <p className="mt-0.5 text-foreground-muted">{provider.description}</p>
    </button>
  );
}
