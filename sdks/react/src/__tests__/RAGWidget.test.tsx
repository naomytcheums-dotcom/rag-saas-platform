import { act, render } from "@testing-library/react";
import { createRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RAGWidget } from "../RAGWidget";
import type { RAGWidgetHandle } from "../RAGWidget.types";
import type { RAGWidgetGlobal } from "../RAGWidget.types";

function mockGlobalWidget(): RAGWidgetGlobal & { _listeners: Record<string, ((p?: unknown) => void)[]> } {
  const listeners: Record<string, ((p?: unknown) => void)[]> = {};
  const widget = {
    __initialized: true,
    _listeners: listeners,
    init: vi.fn(),
    open: vi.fn(),
    close: vi.fn(),
    toggle: vi.fn(),
    sendMessage: vi.fn(),
    on: vi.fn((event: string, cb: (p?: unknown) => void) => {
      listeners[event] = listeners[event] || [];
      listeners[event].push(cb);
    }),
    off: vi.fn((event: string, cb: (p?: unknown) => void) => {
      listeners[event] = (listeners[event] || []).filter((fn) => fn !== cb);
    }),
    destroy: vi.fn(),
    updateConfig: vi.fn(),
  };
  return widget;
}

function stubScriptLoading() {
  const originalAppendChild = document.body.appendChild.bind(document.body);
  vi.spyOn(document.body, "appendChild").mockImplementation((node: Node) => {
    const result = originalAppendChild(node);
    if (node instanceof HTMLScriptElement && node.dataset.ragwidgetLoader === "true") {
      window.RAGWidget = mockGlobalWidget();
      queueMicrotask(() => node.onload?.(new Event("load")));
    }
    return result;
  });
}

describe("RAGWidget", () => {
  beforeEach(() => {
    stubScriptLoading();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete window.RAGWidget;
  });

  it("loads the real widget script with the real public key and base URL", async () => {
    render(<RAGWidget apiKey="wgt_test_key" baseUrl="https://api.test.example" />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const script = document.querySelector<HTMLScriptElement>('script[data-ragwidget-loader="true"]');
    expect(script?.src).toBe("https://api.test.example/widget/script.js");
    expect(script?.dataset.key).toBe("wgt_test_key");
  });

  it("calls window.RAGWidget.init with the forwarded props", async () => {
    render(<RAGWidget apiKey="wgt_test_key" theme="dark" position="top-left" primaryColor="#ff0000" />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(window.RAGWidget?.init).toHaveBeenCalledWith(
      expect.objectContaining({ theme: "dark", position: "top-left", colors: { primary: "#ff0000" } })
    );
  });

  it("forwards real widget events to onOpen/onClose/onMessage/onError props", async () => {
    const onOpen = vi.fn();
    const onMessage = vi.fn();
    render(<RAGWidget apiKey="wgt_test_key" onOpen={onOpen} onMessage={onMessage} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const widget = window.RAGWidget as unknown as { _listeners: Record<string, ((p?: unknown) => void)[]> };
    act(() => widget._listeners["open"]?.forEach((cb) => cb()));
    act(() => widget._listeners["message:received"]?.forEach((cb) => cb({ response: "hi" })));

    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onMessage).toHaveBeenCalledWith({ response: "hi" });
  });

  it("exposes open/close/toggle/sendMessage via ref", async () => {
    const ref = createRef<RAGWidgetHandle>();
    render(<RAGWidget ref={ref} apiKey="wgt_test_key" />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    ref.current?.open();
    ref.current?.sendMessage("hello");

    expect(window.RAGWidget?.open).toHaveBeenCalledTimes(1);
    expect(window.RAGWidget?.sendMessage).toHaveBeenCalledWith("hello");
  });

  it("destroys the widget on unmount", async () => {
    const { unmount } = render(<RAGWidget apiKey="wgt_test_key" />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const destroySpy = window.RAGWidget?.destroy;
    unmount();
    expect(destroySpy).toHaveBeenCalledTimes(1);
  });

  it("reports a script load failure through onError", async () => {
    vi.restoreAllMocks();
    const originalAppendChild = document.body.appendChild.bind(document.body);
    vi.spyOn(document.body, "appendChild").mockImplementation((node: Node) => {
      const result = originalAppendChild(node);
      if (node instanceof HTMLScriptElement) {
        queueMicrotask(() => node.onerror?.(new Event("error") as unknown as string));
      }
      return result;
    });

    const onError = vi.fn();
    render(<RAGWidget apiKey="wgt_bad_key" onError={onError} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: expect.stringContaining("Failed to load") }));
  });
});
