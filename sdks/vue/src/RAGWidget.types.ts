export interface RAGWidgetProps {
  apiKey: string;
  baseUrl?: string;
  agentId?: string;
  position?: "bottom-right" | "bottom-left" | "top-right" | "top-left";
  theme?: "light" | "dark" | "auto";
  language?: string;
  primaryColor?: string;
  logo?: string;
  welcomeMessage?: string;
  suggestedQuestions?: string[];
}

/** Mirrors sdks/js's own `window.RAGWidget` global (Partie 9.2.11/9.3.14) --
 * this package is a thin wrapper AROUND that real, already-built
 * embeddable script, not a second, parallel widget implementation
 * (same real design as sdks/react -- see that package's own README). */
export interface RAGWidgetGlobal {
  __initialized: boolean;
  init: (overrides?: Record<string, unknown>) => void;
  open: () => void;
  close: () => void;
  toggle: () => void;
  sendMessage: (message: string) => void;
  on: (event: string, cb: (payload?: unknown) => void) => void;
  off: (event: string, cb: (payload?: unknown) => void) => void;
  destroy: () => void;
  updateConfig: (partial: Record<string, unknown>) => void;
}

declare global {
  interface Window {
    RAGWidget?: RAGWidgetGlobal;
  }
}
