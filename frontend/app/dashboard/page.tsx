"use client";

import Link from "next/link";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

const QUICK_LINKS = [
  { href: "/chat", label: "Open chat", description: "Talk to your agents" },
  { href: "/dashboard/documents", label: "Documents", description: "Upload and manage knowledge" },
  { href: "/dashboard/agents", label: "Agents", description: "Configure prompts and tools" },
  { href: "/dashboard/settings/api-keys", label: "API keys", description: "Public API access" },
  { href: "/dashboard/settings/webhooks", label: "Webhooks", description: "Real-time event delivery" },
  { href: "/dashboard/settings/widget", label: "Widget", description: "Embed the chatbot on your site" },
  { href: "/dashboard/settings/integrations", label: "Integrations", description: "Slack, Teams, Discord" },
  { href: "/dashboard/settings/organization", label: "Organization", description: "Team and branding" },
];

export default function DashboardHome() {
  const { org, loading } = useCurrentOrg();

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold text-foreground">
        {loading ? "…" : org?.name ?? "Your workspace"}
      </h1>
      <p className="mt-1 text-sm text-foreground-muted">Everything you need to run your RAG platform.</p>

      <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {QUICK_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="flex items-start gap-3 rounded-xl border border-border bg-surface p-4 hover:border-accent hover:bg-accent-soft/40"
          >
            <div>
              <p className="text-sm font-medium text-foreground">{link.label}</p>
              <p className="text-xs text-foreground-muted">{link.description}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
