"use client";

import { useState } from "react";
import { DatasetList } from "@/components/fine-tuning/DatasetList";
import { DatasetUpload } from "@/components/fine-tuning/DatasetUpload";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

export default function Page() {
  const { org, loading } = useCurrentOrg();
  const [refreshKey, setRefreshKey] = useState(0);

  if (loading || !org) return <p className="mx-auto max-w-4xl text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold text-foreground">Fine-tuning datasets</h1>
      <div className="mt-4">
        <DatasetUpload orgId={org.id} onUploaded={() => setRefreshKey((k) => k + 1)} />
      </div>
      <div className="mt-5">
        <DatasetList key={refreshKey} orgId={org.id} />
      </div>
    </div>
  );
}
