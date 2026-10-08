"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import LoadingState from "@/components/LoadingState";

// Platform business metrics belong to the super-admin area (the API answers 403 to anyone else).
export default function Page() {
  const router = useRouter();
  useEffect(() => { router.replace("/admin?tab=Business"); }, [router]);
  return <LoadingState fullScreen={false} />;
}
