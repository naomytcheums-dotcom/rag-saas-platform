// Specs 8.1.14 / 8.1.16: export the conversation (PDF, DOCX, JSON, Markdown) and switch it between public and private.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const patch = vi.fn();

const translation = { t: (key: string) => key };
vi.mock("@/lib/i18n", () => ({ useTranslation: () => translation }));
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;
    detail: unknown;
    constructor(status: number, detail: unknown) {
      super(String(detail));
      this.status = status;
      this.detail = detail;
    }
  }
  return { api: { patch: (...a: unknown[]) => patch(...a) }, ApiError, fileUrl: (p: string) => `http://api.test${p}` };
});

import ConversationTools from "./ConversationTools";

const fetchMock = vi.fn();

beforeEach(() => {
  patch.mockReset();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  window.localStorage.setItem("access_token", "tok");
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ConversationTools", () => {
  it("renders nothing without a conversation", () => {
    const { container } = render(<ConversationTools conversationId={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("downloads the chosen format with the bearer token", async () => {
    fetchMock.mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(["x"])) });
    render(<ConversationTools conversationId="c1" />);
    await userEvent.selectOptions(screen.getByLabelText("chat.export"), "pdf");
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/conversations/c1/export/pdf");
    expect(init.headers).toEqual({ Authorization: "Bearer tok" });
  });

  it("shows an error when the export fails", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 500, text: () => Promise.resolve("boom") });
    render(<ConversationTools conversationId="c1" />);
    await userEvent.selectOptions(screen.getByLabelText("chat.export"), "docx");
    expect(await screen.findByRole("alert")).toHaveTextContent("chat.export_error");
  });

  it("toggles the visibility through the API", async () => {
    patch.mockResolvedValue({ is_public: true });
    render(<ConversationTools conversationId="c1" />);
    await userEvent.click(screen.getByRole("button", { name: "chat.visibility_private" }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith("/conversations/c1/visibility", { is_public: true }));
    expect(await screen.findByRole("button", { name: "chat.visibility_public" })).toHaveAttribute("aria-pressed", "true");
  });
});
