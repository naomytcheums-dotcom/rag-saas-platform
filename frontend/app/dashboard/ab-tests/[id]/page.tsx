"use client";

import { use } from "react";
import { ABTestDetail } from "@/components/ab-tests/ABTestDetail";

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <ABTestDetail testId={id} />;
}
