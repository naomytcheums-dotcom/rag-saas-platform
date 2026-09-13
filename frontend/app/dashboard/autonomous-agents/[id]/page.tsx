"use client";

import { use } from "react";
import { AgentDetail } from "@/components/autonomous/AgentDetail";

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <div className="mx-auto max-w-4xl">
      <AgentDetail agentId={id} />
    </div>
  );
}
