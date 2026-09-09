import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRAGWidget, useRAGWidgetConfig, useRAGWidgetMessages } from "../hooks";
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

describe("useRAGWidget", () => {
  beforeEach(() => installMockWidget());
  afterEach(() => { delete window.RAGWidget; });

  it("calls through to the real global widget's imperative methods", () => {
    const { result } = renderHook(() => useRAGWidget());
    result.current.open();
    result.current.sendMessage("hi");
    expect(window.RAGWidget?.open).toHaveBeenCalledTimes(1);
    expect(window.RAGWidget?.sendMessage).toHaveBeenCalledWith("hi");
  });
});

describe("useRAGWidgetConfig", () => {
  beforeEach(() => installMockWidget());
  afterEach(() => { delete window.RAGWidget; });

  it("forwards to updateConfig", () => {
    const { result } = renderHook(() => useRAGWidgetConfig());
    result.current({ theme: "dark" });
    expect(window.RAGWidget?.updateConfig).toHaveBeenCalledWith({ theme: "dark" });
  });
});

describe("useRAGWidgetMessages", () => {
  let listeners: Record<string, ((p?: unknown) => void)[]>;

  beforeEach(() => {
    ({ listeners } = installMockWidget());
  });
  afterEach(() => { delete window.RAGWidget; });

  it("accumulates real sent and received messages in order", () => {
    const { result } = renderHook(() => useRAGWidgetMessages());

    act(() => listeners["message:sent"]?.forEach((cb) => cb({ message: "Hi" })));
    act(() => listeners["message:received"]?.forEach((cb) => cb({ response: "Hello!" })));

    expect(result.current).toEqual([
      { role: "user", text: "Hi" },
      { role: "assistant", text: "Hello!" },
    ]);
  });
});
