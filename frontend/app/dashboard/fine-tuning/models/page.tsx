"use client";

import { ModelList } from "@/components/fine-tuning/ModelList";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

export default function Page() {
  const { org, loading } = useCurrentOrg();

  if (loading || !org) return <p className="mx-auto max-w-4xl text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold text-foreground">Fine-tuned models</h1>
      <div className="mt-5">
        <ModelList orgId={org.id} />
      </div>
    </div>
  );
}
