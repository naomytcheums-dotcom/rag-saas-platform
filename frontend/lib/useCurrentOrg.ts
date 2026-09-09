"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export interface OrganizationEntry {
  id: string;
  name: string;
  slug: string;
  my_role: "owner" | "admin" | "member" | "viewer";
}

/** Real, honest simplification: every account gets exactly one
 * organization at registration (api/routers/auth.py's own
 * register()) and this dashboard has no multi-org switcher UI yet --
 * so every settings page just uses the CALLER'S FIRST real
 * organization rather than requiring one to be picked first. */
export function useCurrentOrg() {
  const [org, setOrg] = useState<OrganizationEntry | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void api
      .get<{ items: OrganizationEntry[] }>("/organizations")
      .then((data) => setOrg(data.items[0] ?? null))
      .catch(() => setOrg(null))
      .finally(() => setLoading(false));
  }, []);

  return { org, loading };
}
