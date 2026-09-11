"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import ProviderCard from "./ProviderCard";

interface Provider {
  id: string;
  name: string;
  description: string;
}

interface ProviderListProps {
  selected: string;
  onSelect: (id: string) => void;
}

// Partie 15.1 -- GET /integrations/providers (flat, unauthenticated --
// this is a static catalog, not org-scoped data).
export default function ProviderList({ selected, onSelect }: ProviderListProps) {
  const [providers, setProviders] = useState<Provider[]>([]);

  useEffect(() => {
    void api.get<Provider[]>("/integrations/providers").then(setProviders).catch(() => setProviders([]));
  }, []);

  if (providers.length === 0) return null;

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {providers.map((provider) => (
        <ProviderCard key={provider.id} provider={provider} selected={selected === provider.id} onSelect={onSelect} />
      ))}
    </div>
  );
}
