import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import RAGWidget from "../RAGWidget.vue";
import type { RAGWidgetGlobal } from "../RAGWidget.types";

function mockGlobalWidget() {
  const listeners: Record<string, ((p?: unknown) => void)[]> = {};
  const widget: RAGWidgetGlobal = {
    __initialized: true,
    init: vi.fn(),
    open: vi.fn(),
    close: vi.fn(),
    toggle: vi.fn(),
    sendMessage: vi.fn(),
    on: vi.fn((event, cb) => {
      listeners[event] = listeners[event] || [];
      listeners[event].push(cb);
    }),
    off: vi.fn(),
    destroy: vi.fn(),
    updateConfig: vi.fn(),
  };
  return { widget, listeners };
}

function stubScriptLoading() {
  const originalAppendChild = document.body.appendChild.bind(document.body);
  vi.spyOn(document.body, "appendChild").mockImplementation((node: Node) => {
    const result = originalAppendChild(node);
    if (node instanceof HTMLScriptElement && node.dataset.ragwidgetLoader === "true") {
      const { widget } = mockGlobalWidget();
      window.RAGWidget = widget;
      queueMicrotask(() => node.onload?.(new Event("load")));
    }
    return result;
  });
}

describe("RAGWidget.vue", () => {
  beforeEach(() => stubScriptLoading());
  afterEach(() => {
    vi.restoreAllMocks();
    delete window.RAGWidget;
  });

  it("loads the real widget script with the real public key and base URL", async () => {
    mount(RAGWidget, { props: { apiKey: "wgt_test_key", baseUrl: "https://api.test.example" } });
    await Promise.resolve();
    await Promise.resolve();

    const script = document.querySelector<HTMLScriptElement>('script[data-ragwidget-loader="true"]');
    expect(script?.src).toBe("https://api.test.example/widget/script.js");
    expect(script?.dataset.key).toBe("wgt_test_key");
  });

  it("calls window.RAGWidget.init with the forwarded props", async () => {
    mount(RAGWidget, { props: { apiKey: "wgt_test_key", theme: "dark", position: "top-left" } });
    await Promise.resolve();
    await Promise.resolve();

    expect(window.RAGWidget?.init).toHaveBeenCalledWith(expect.objectContaining({ theme: "dark", position: "top-left" }));
  });

  it("emits real open/message events from the underlying widget", async () => {
    const wrapper = mount(RAGWidget, { props: { apiKey: "wgt_test_key" } });
    await Promise.resolve();
    await Promise.resolve();

    const widget = window.RAGWidget as unknown as { on: ReturnType<typeof vi.fn> };
    const openHandler = widget.on.mock.calls.find(([event]) => event === "open")?.[1];
    openHandler?.();

    expect(wrapper.emitted("open")).toHaveLength(1);
  });

  it("exposes open/close/toggle/sendMessage", async () => {
    const wrapper = mount(RAGWidget, { props: { apiKey: "wgt_test_key" } });
    await Promise.resolve();
    await Promise.resolve();

    (wrapper.vm as unknown as { open: () => void }).open();
    expect(window.RAGWidget?.open).toHaveBeenCalledTimes(1);
  });

  it("destroys the widget on unmount", async () => {
    const wrapper = mount(RAGWidget, { props: { apiKey: "wgt_test_key" } });
    await Promise.resolve();
    await Promise.resolve();

    const destroySpy = window.RAGWidget?.destroy;
    wrapper.unmount();
    expect(destroySpy).toHaveBeenCalledTimes(1);
  });
});
