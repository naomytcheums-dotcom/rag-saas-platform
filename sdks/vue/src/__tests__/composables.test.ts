import { mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRAGWidget, useRAGWidgetConfig, useRAGWidgetMessages } from "../composables";
import type { RAGWidgetGlobal } from "../RAGWidget.types";

function installMockWidget() {
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
  window.RAGWidget = widget;
  return { widget, listeners };
}

function mountWithSetup<T>(setup: () => T) {
  let exposed!: T;
  const Wrapper = defineComponent({
    setup() {
      exposed = setup();
      return () => h("div");
    },
  });
  mount(Wrapper);
  return exposed;
}

describe("useRAGWidget", () => {
  beforeEach(() => installMockWidget());
  afterEach(() => { delete window.RAGWidget; });

  it("calls through to the real global widget", () => {
    const { open, sendMessage } = mountWithSetup(() => useRAGWidget());
    open();
    sendMessage("hi");
    expect(window.RAGWidget?.open).toHaveBeenCalledTimes(1);
    expect(window.RAGWidget?.sendMessage).toHaveBeenCalledWith("hi");
  });
});

describe("useRAGWidgetConfig", () => {
  beforeEach(() => installMockWidget());
  afterEach(() => { delete window.RAGWidget; });

  it("forwards to updateConfig", () => {
    const updateConfig = mountWithSetup(() => useRAGWidgetConfig());
    updateConfig({ theme: "dark" });
    expect(window.RAGWidget?.updateConfig).toHaveBeenCalledWith({ theme: "dark" });
  });
});

describe("useRAGWidgetMessages", () => {
  let listeners: Record<string, ((p?: unknown) => void)[]>;

  beforeEach(() => { ({ listeners } = installMockWidget()); });
  afterEach(() => { delete window.RAGWidget; });

  it("accumulates real sent and received messages in order", () => {
    const messages = mountWithSetup(() => useRAGWidgetMessages());

    listeners["message:sent"]?.forEach((cb) => cb({ message: "Hi" }));
    listeners["message:received"]?.forEach((cb) => cb({ response: "Hello!" }));

    expect(messages.value).toEqual([
      { role: "user", text: "Hi" },
      { role: "assistant", text: "Hello!" },
    ]);
  });
});
