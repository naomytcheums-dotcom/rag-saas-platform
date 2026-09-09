import { useEffect, useImperativeHandle, useRef, forwardRef } from "react";
import type { RAGWidgetHandle, RAGWidgetProps } from "./RAGWidget.types";

const DEFAULT_BASE_URL = "https://api.ragsaasplatform.com";

function loadScript(src: string, dataset: Record<string, string>): Promise<void> {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[data-ragwidget-loader="true"]`);
    if (existing) {
      existing.remove();
    }
    const script = document.createElement("script");
    script.src = src;
    script.dataset.ragwidgetLoader = "true";
    Object.entries(dataset).forEach(([key, value]) => {
      script.setAttribute(`data-${key}`, value);
    });
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load the RAG widget script from ${src}`));
    document.body.appendChild(script);
  });
}

/**
 * Official React wrapper around the real, already-built embeddable
 * widget script (frontend/widget/embed.js, served at
 * `/widget/script.js`) -- see RAGWidget.types.ts's own top docstring.
 * Real, deliberate design: this component does NOT reimplement the
 * chat UI in React (that UI lives inside a real, sandboxed iframe the
 * script itself manages) -- it only owns the real script's lifecycle
 * (load once, wire real events to React props, clean up on unmount).
 */
export const RAGWidget = forwardRef<RAGWidgetHandle, RAGWidgetProps>(function RAGWidget(props, ref) {
  const { apiKey, baseUrl = DEFAULT_BASE_URL, agentId, position, theme, language, primaryColor, logo, welcomeMessage, suggestedQuestions, onOpen, onClose, onMessage, onError } = props;
  const propsRef = useRef(props);
  propsRef.current = props;

  useImperativeHandle(ref, () => ({
    open: () => window.RAGWidget?.open(),
    close: () => window.RAGWidget?.close(),
    toggle: () => window.RAGWidget?.toggle(),
    sendMessage: (message: string) => window.RAGWidget?.sendMessage(message),
  }), []);

  useEffect(() => {
    let cancelled = false;

    const dataset: Record<string, string> = { key: apiKey, "base-url": baseUrl, "manual-init": "true" };

    loadScript(`${baseUrl}/widget/script.js`, dataset)
      .then(() => {
        if (cancelled || !window.RAGWidget) return;

        const handleOpen = () => propsRef.current.onOpen?.();
        const handleClose = () => propsRef.current.onClose?.();
        const handleMessage = (payload?: unknown) => propsRef.current.onMessage?.(payload);
        const handleError = (payload?: unknown) => propsRef.current.onError?.(payload as { message: string });

        window.RAGWidget.on("open", handleOpen);
        window.RAGWidget.on("close", handleClose);
        window.RAGWidget.on("message:received", handleMessage);
        window.RAGWidget.on("error", handleError);

        window.RAGWidget.init({
          agent_id: agentId, position, theme, language,
          colors: primaryColor ? { primary: primaryColor } : undefined,
          logo_url: logo, welcome_message: welcomeMessage, suggested_questions: suggestedQuestions,
        });

        return () => {
          window.RAGWidget?.off("open", handleOpen);
          window.RAGWidget?.off("close", handleClose);
          window.RAGWidget?.off("message:received", handleMessage);
          window.RAGWidget?.off("error", handleError);
        };
      })
      .catch((err: Error) => propsRef.current.onError?.({ message: err.message }));

    return () => {
      cancelled = true;
      window.RAGWidget?.destroy();
    };
    // Re-init only when the real, load-bearing identity of the widget
    // changes -- baseUrl/apiKey determine WHICH script/org this is;
    // every other prop is applied via updateConfig below instead of a
    // full script reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey, baseUrl]);

  useEffect(() => {
    window.RAGWidget?.updateConfig({
      agent_id: agentId, position, theme, language,
      colors: primaryColor ? { primary: primaryColor } : undefined,
      logo_url: logo, welcome_message: welcomeMessage, suggested_questions: suggestedQuestions,
    });
  }, [agentId, position, theme, language, primaryColor, logo, welcomeMessage, suggestedQuestions]);

  return null;
});
