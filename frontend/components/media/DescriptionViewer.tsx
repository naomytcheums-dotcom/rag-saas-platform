"use client";

import type { MediaAsset } from "@/lib/services/media";

export function DescriptionViewer({ asset }: { asset: MediaAsset }) {
  if (!asset.description && !asset.ocr_text && !asset.objects_json?.length) {
    return <p className="text-xs text-foreground-muted">No description yet.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {asset.description && <p className="text-sm text-foreground">{asset.description}</p>}
      {!!asset.objects_json?.length && (
        <div className="flex flex-wrap gap-1.5">
          {asset.objects_json.map((object) => (
            <span key={object} className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent">{object}</span>
          ))}
        </div>
      )}
      {asset.ocr_text && (
        <div>
          <p className="text-xs font-medium text-foreground-muted">Texte détecté (OCR)</p>
          <p className="mt-1 whitespace-pre-wrap rounded-lg border border-border bg-surface-muted p-3 text-sm text-foreground">{asset.ocr_text}</p>
        </div>
      )}
    </div>
  );
}
