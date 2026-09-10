"use client";

import { getVoiceErrorAction, getVoiceErrorMessage, type VoiceErrorType } from "@/lib/voiceErrors";

interface VoiceErrorProps {
  type: VoiceErrorType;
  onRetry?: () => void;
}

// Partie 8.2.12 -- a clear, real error message plus a recommended
// action, with a real retry button when the error is recoverable.
export default function VoiceError({ type, onRetry }: VoiceErrorProps) {
  return (
    <div role="alert" className="flex items-start gap-2 rounded-lg border border-danger-soft bg-danger-soft/60 p-3 text-sm">
      <div className="flex-1">
        <p className="font-medium text-danger">{getVoiceErrorMessage(type)}</p>
        <p className="text-foreground-muted">{getVoiceErrorAction(type)}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent-hover"
        >
          Retry
        </button>
      )}
    </div>
  );
}
