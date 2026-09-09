import { onBeforeUnmount, onMounted, ref, watch, type Ref } from "vue";
import type { RAGWidgetGlobal, RAGWidgetProps } from "./RAGWidget.types";

const DEFAULT_BASE_URL = "https://api.ragsaasplatform.com";

function loadScript(src: string, dataset: Record<string, string>): Promise<void> {
  return new Promise((resolve, reject) => {
    document.querySelector('script[data-ragwidget-loader="true"]')?.remove();
    const script = document.createElement("script");
    script.src = src;
    script.dataset.ragwidgetLoader = "true";
    Object.entries(dataset).forEach(([key, value]) => script.setAttribute(`data-${key}`, value));
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load the RAG widget script from ${src}`));
    document.body.appendChild(script);
  });
}

/** Real composable powering `RAGWidget.vue` -- owns the real script's
 * lifecycle (Vue 3 Composition API: `onMounted`/`onBeforeUnmount`,
 * `watch` for live config updates), mirroring `sdks/react`'s own
 * `RAGWidget.tsx` hook usage 1:1. */
export function useRAGWidgetLifecycle(props: Ref<RAGWidgetProps>, emit: (event: "open" | "close" | "message" | "error", payload?: unknown) => void) {
  const ready = ref(false);

  onMounted(async () => {
    try {
      await loadScript(`${props.value.baseUrl ?? DEFAULT_BASE_URL}/widget/script.js`, {
        key: props.value.apiKey, "base-url": props.value.baseUrl ?? DEFAULT_BASE_URL, "manual-init": "true",
      });
    } catch (err) {
      emit("error", { message: (err as Error).message });
      return;
    }

    const widget = window.RAGWidget;
    if (!widget) return;

    widget.on("open", () => emit("open"));
    widget.on("close", () => emit("close"));
    widget.on("message:received", (payload) => emit("message", payload));
    widget.on("error", (payload) => emit("error", payload));

    widget.init(configFromProps(props.value));
    ready.value = true;
  });

  watch(props, (next) => {
    if (ready.value) window.RAGWidget?.updateConfig(configFromProps(next));
  }, { deep: true });

  onBeforeUnmount(() => {
    window.RAGWidget?.destroy();
  });

  return {
    ready,
    open: () => window.RAGWidget?.open(),
    close: () => window.RAGWidget?.close(),
    toggle: () => window.RAGWidget?.toggle(),
    sendMessage: (message: string) => window.RAGWidget?.sendMessage(message),
  };
}

function configFromProps(props: RAGWidgetProps): Record<string, unknown> {
  return {
    agent_id: props.agentId, position: props.position, theme: props.theme, language: props.language,
    colors: props.primaryColor ? { primary: props.primaryColor } : undefined,
    logo_url: props.logo, welcome_message: props.welcomeMessage, suggested_questions: props.suggestedQuestions,
  };
}

/** Item 3's own literal `useRAGWidget()` -- the imperative control
 * surface, usable from ANY component once `<RAGWidget>` is mounted
 * somewhere in the tree, without needing a template ref to it. */
export function useRAGWidget() {
  return {
    open: () => window.RAGWidget?.open(),
    close: () => window.RAGWidget?.close(),
    toggle: () => window.RAGWidget?.toggle(),
    sendMessage: (message: string) => window.RAGWidget?.sendMessage(message),
  };
}

export function useRAGWidgetConfig() {
  return (partial: Record<string, unknown>) => window.RAGWidget?.updateConfig(partial);
}

export function useRAGWidgetEvents(event: string, callback: (payload?: unknown) => void) {
  onMounted(() => window.RAGWidget?.on(event, callback));
  onBeforeUnmount(() => window.RAGWidget?.off(event, callback));
}

export function useRAGWidgetMessages() {
  const messages = ref<{ role: "user" | "assistant"; text: string }[]>([]);

  useRAGWidgetEvents("message:sent", (payload) => {
    const message = (payload as { message?: string })?.message;
    if (message) messages.value.push({ role: "user", text: message });
  });
  useRAGWidgetEvents("message:received", (payload) => {
    const text = (payload as { response?: string })?.response;
    if (text) messages.value.push({ role: "assistant", text });
  });

  return messages;
}
