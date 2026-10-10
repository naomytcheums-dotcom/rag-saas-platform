// Specs 2.1.10 / 2.1.11 / 2.1.12 / 2.1.16: import from a URL, a sitemap, GitHub or Notion.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
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
  return { api: { post: (...a: unknown[]) => post(...a) }, ApiError };
});

import ImportSources from "./ImportSources";

beforeEach(() => post.mockReset());

describe("ImportSources", () => {
  it("imports a URL and refreshes the list", async () => {
    post.mockResolvedValue({});
    const onImported = vi.fn();
    render(<ImportSources orgId="org-1" onImported={onImported} />);
    await userEvent.type(screen.getByLabelText("documents.import_target"), "https://example.com/a");
    await userEvent.click(screen.getByRole("button", { name: "documents.import_button" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/organizations/org-1/documents/url", { url: "https://example.com/a" }));
    expect(onImported).toHaveBeenCalled();
    expect(await screen.findByRole("status")).toHaveTextContent("documents.import_started");
  });

  it.each([
    ["sitemap", "documents/sitemap", { url: "https://example.com/sitemap.xml" }, "https://example.com/sitemap.xml"],
    ["github", "documents/github/repo", { repo_url: "https://github.com/o/r" }, "https://github.com/o/r"],
    ["notion", "documents/notion", { url_or_id: "abc123", kind: "page" }, "abc123"],
  ])("sends the right route and body for %s", async (source, path, body, typed) => {
    post.mockResolvedValue({});
    render(<ImportSources orgId="org-1" onImported={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("documents.import_source"), source);
    await userEvent.type(screen.getByLabelText("documents.import_target"), typed);
    await userEvent.click(screen.getByRole("button", { name: "documents.import_button" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith(`/organizations/org-1/${path}`, body));
  });

  it("disables the button while the field is empty", () => {
    render(<ImportSources orgId="org-1" onImported={vi.fn()} />);
    expect(screen.getByRole("button", { name: "documents.import_button" })).toBeDisabled();
  });
});
