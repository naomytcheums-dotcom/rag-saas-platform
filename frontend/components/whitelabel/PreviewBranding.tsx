"use client";

import { useWhiteLabelPreview } from "@/lib/hooks/useWhiteLabelPreview";

interface PreviewBrandingProps {
  orgId: string;
}

export function PreviewBranding({ orgId }: PreviewBrandingProps) {
  const { preview, loading, error } = useWhiteLabelPreview(orgId);

  if (loading) return <p className="text-sm text-foreground-muted">Loading preview…</p>;
  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (!preview) return null;

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <div className="flex items-center gap-3 px-4 py-3" style={{ backgroundColor: preview.primary_color, fontFamily: preview.font_family }}>
        {preview.logo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview.logo_url} alt="" className="h-6 max-w-[120px] object-contain" />
        ) : (
          <span className="text-sm font-semibold text-white">{preview.brand_name ?? "RAG SaaS"}</span>
        )}
      </div>
      <div className="bg-surface p-4">
        <div className="flex gap-2">
          <span className="rounded-full px-3 py-1 text-xs font-medium text-white" style={{ backgroundColor: preview.primary_color }}>Primary button</span>
          <span className="rounded-full px-3 py-1 text-xs font-medium text-white" style={{ backgroundColor: preview.secondary_color }}>Secondary</span>
          <span className="rounded-full px-3 py-1 text-xs font-medium text-white" style={{ backgroundColor: preview.accent_color }}>Accent</span>
        </div>
        {!preview.is_active && (
          <p className="mt-3 text-xs text-foreground-muted">White-label is currently turned off -- this preview shows the platform's own real defaults.</p>
        )}
      </div>
    </div>
  );
}
