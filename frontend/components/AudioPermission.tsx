"use client";

import { useAudioPermission } from "@/hooks/useAudioPermission";

interface AudioPermissionProps {
  children: React.ReactNode;
}

// Partie 8.2.11 -- gates its children behind a real, granted
// microphone permission; shows a real request prompt or a real,
// clear denied state (with a link to the browser's own site settings)
// otherwise.
export default function AudioPermission({ children }: AudioPermissionProps) {
  const { status, canRetry, requestPermission } = useAudioPermission();

  if (status === "granted") return <>{children}</>;

  if (status === "denied") {
    return (
      <div role="alert" className="rounded-lg border border-border bg-surface-muted p-3 text-sm">
        <p className="font-medium text-foreground">Microphone access is blocked.</p>
        <p className="mt-1 text-foreground-muted">
          Voice features need microphone access. Allow it in your browser&apos;s site settings, then reload this page.
        </p>
        {canRetry && (
          <button
            type="button"
            onClick={() => void requestPermission()}
            className="mt-2 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover"
          >
            Try again
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-surface-muted p-3 text-sm">
      <p className="text-foreground">Voice features need microphone access.</p>
      <button
        type="button"
        onClick={() => void requestPermission()}
        className="mt-2 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover"
      >
        Allow microphone
      </button>
    </div>
  );
}
