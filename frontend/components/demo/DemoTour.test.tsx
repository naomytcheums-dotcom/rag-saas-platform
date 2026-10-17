// Specs 14.2.7 / 14.3.2: the interactive demo renders the recorded steps, moves between them with the buttons and the arrow keys, and says so when its assets are missing.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/i18n", async () => {
  const en = (await import("@/lib/locales/en.json")).default as Record<string, string>;
  return { useTranslation: () => ({ language: "en", setLanguage: () => {}, t: (key: string, params?: Record<string, string | number>) => Object.entries(params ?? {}).reduce((text, [name, value]) => text.replaceAll(`{${name}}`, String(value)), en[key] ?? key) }) };
});

import DemoTour from "./DemoTour";

const manifest = {
  recorded: "2026-10-13",
  video: { src: "/demo/product-tour.mp4", poster: "/demo/poster.jpg", captions: "/demo/product-tour.vtt" },
  steps: [
    { id: "register", title: "Create an account", caption: "Sign up with an e-mail address.", image: "/demo/01.png", alt: "Registration form", video_at: 0 },
    { id: "upload", title: "Upload a document", caption: "Drop a file.", image: "/demo/02.png", alt: "Documents page", video_at: 12 },
    { id: "chat", title: "Ask a question", caption: "Read the cited answer.", image: "/demo/03.png", alt: "Chat answer", video_at: 65 },
  ],
};

afterEach(() => { vi.restoreAllMocks(); });

function serve(body: unknown, ok = true) {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok, status: ok ? 200 : 404, json: async () => body })));
}

describe("DemoTour", () => {
  it("shows the first recorded step, the video with captions and the recording date", async () => {
    serve(manifest);
    const { container } = render(<DemoTour />);
    expect(await screen.findByRole("heading", { name: "Create an account" })).toBeTruthy();
    expect(screen.getByAltText("Registration form").getAttribute("src")).toBe("/demo/01.png");
    expect(container.querySelector("video source")?.getAttribute("src")).toBe("/demo/product-tour.mp4");
    expect(container.querySelector("video track")?.getAttribute("src")).toBe("/demo/product-tour.vtt");
    expect(screen.getByText("Step 1 of 3")).toBeTruthy();
    expect(screen.getByText(/Recorded on 2026-10-13/)).toBeTruthy();
  });

  it("moves with the buttons, the step list and the arrow keys, and stops at both ends", async () => {
    serve(manifest);
    render(<DemoTour />);
    await screen.findByRole("heading", { name: "Create an account" });
    const previous = screen.getByRole("button", { name: "Previous" }) as HTMLButtonElement;
    const next = screen.getByRole("button", { name: "Next" }) as HTMLButtonElement;
    expect(previous.disabled).toBe(true);
    fireEvent.click(next);
    expect(screen.getByRole("heading", { name: "Upload a document" })).toBeTruthy();
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(screen.getByText("Step 3 of 3")).toBeTruthy();
    expect(next.disabled).toBe(true);
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(screen.getByText("Step 3 of 3")).toBeTruthy();
    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(screen.getByRole("heading", { name: "Upload a document" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Create an account/ }));
    expect(screen.getByText("Step 1 of 3")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Create an account/ }).getAttribute("aria-current")).toBe("step");
  });

  it("seeks the video to the moment of the current step", async () => {
    serve(manifest);
    const { container } = render(<DemoTour />);
    await screen.findByRole("heading", { name: "Create an account" });
    const video = container.querySelector("video") as HTMLVideoElement;
    Object.defineProperty(video, "play", { value: vi.fn(async () => {}) });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: /1:05/ }));
    expect(video.currentTime).toBe(65);
  });

  it("says plainly that the recording is unavailable instead of showing an empty page", async () => {
    serve({}, false);
    render(<DemoTour />);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("could not be loaded"));
  });

  it("refuses a manifest without steps", async () => {
    serve({ ...manifest, steps: [] });
    render(<DemoTour />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
  });
});
