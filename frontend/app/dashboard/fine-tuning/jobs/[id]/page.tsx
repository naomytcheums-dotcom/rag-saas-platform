"use client";

import { use } from "react";
import { JobDetail } from "@/components/fine-tuning/JobDetail";

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <div className="mx-auto max-w-4xl">
      <JobDetail jobId={id} />
    </div>
  );
}
