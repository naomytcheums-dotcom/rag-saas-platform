import { useCallback, useEffect, useState } from "react";
import type { RAGWidgetHandle } from "./RAGWidget.types";

/** Real, generic event subscription -- every other hook below is
 * built on top of this ONE real subscription primitive rather than
 * each hook re-implementing its own add/removeEventListener pair. */
export function useRAGWidgetEvents(event: string, callback: (payload?: unknown) => void): void {
  useEffect(() => {
    const widget = window.RAGWidget;
    if (!widget) return;
    widget.on(event, callback);
    return () => widget.off(event, callback);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [event, callback]);
}

/** Imperative control surface -- open/close/toggle/sendMessage,
 * without needing a `ref` to the `<RAGWidget>` element itself. */
export function useRAGWidget(): RAGWidgetHandle {
  return {
    open: useCallback(() => window.RAGWidget?.open(), []),
    close: useCallback(() => window.RAGWidget?.close(), []),
    toggle: useCallback(() => window.RAGWidget?.toggle(), []),
    sendMessage: useCallback((message: string) => window.RAGWidget?.sendMessage(message), []),
  };
}

/** Real, live config -- `updateConfig` (real overrides) with no
 * separate config-fetching logic here; the widget's own script
 * already fetched its real config once at init. */
export function useRAGWidgetConfig(): (partial: Record<string, unknown>) => void {
  return useCallback((partial: Record<string, unknown>) => window.RAGWidget?.updateConfig(partial), []);
}

/** Real, accumulated in-memory message history -- subscribes to the
 * SAME real `message:sent`/`message:received` events the widget's own
 * script (frontend/widget/embed.js) already emits, rather than a
 * second, parallel message store. */
export function useRAGWidgetMessages(): { role: "user" | "assistant"; text: string }[] {
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; text: string }[]>([]);

  useRAGWidgetEvents("message:sent", useCallback((payload) => {
    const message = (payload as { message?: string })?.message;
    if (message) setMessages((prev) => [...prev, { role: "user", text: message }]);
  }, []));

  useRAGWidgetEvents("message:received", useCallback((payload) => {
    const text = (payload as { response?: string })?.response;
    if (text) setMessages((prev) => [...prev, { role: "assistant", text }]);
  }, []));

  return messages;
}
