"use client";

import { use } from "react";
import { MediaDetail } from "@/components/media/MediaDetail";

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <div className="mx-auto max-w-4xl">
      <MediaDetail mediaAssetId={id} />
    </div>
  );
}
