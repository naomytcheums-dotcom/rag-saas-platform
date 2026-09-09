export interface RAGWidgetProps {
  /** The widget's real, non-secret public key (`wgt_...`) -- NEVER a
   * real, secret OrganizationAPIKey. See api/security/widget_auth.py's
   * own top docstring for why these are deliberately different
   * credentials. */
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
  onOpen?: () => void;
  onClose?: () => void;
  onMessage?: (payload: unknown) => void;
  onError?: (error: { message: string }) => void;
}

export interface RAGWidgetHandle {
  open: () => void;
  close: () => void;
  toggle: () => void;
  sendMessage: (message: string) => void;
}

/** Mirrors sdks/js's own `window.RAGWidget` global (Partie 9.2.11/9.3.14) --
 * this package is a thin wrapper AROUND that real, already-built
 * embeddable script, not a second, parallel widget implementation. */
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
