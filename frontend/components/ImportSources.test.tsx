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

import { ApiError } from "@/lib/api";
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

  it.each([
    ["github_issues", "documents/github/issues", { repo_url: "https://github.com/o/r" }, "https://github.com/o/r"],
    ["google_drive", "documents/google-drive", { drive_id: "1AbC" }, "1AbC"],
    ["google_docs", "documents/google-docs", { document_url_or_id: "1DoC" }, "1DoC"],
    ["confluence", "documents/confluence", { url_or_id: "12345" }, "12345"],
    ["onedrive", "documents/onedrive", { folder_id: "01ABC" }, "01ABC"],
  ])("sends the right route and body for %s (specs 2.1.13 to 2.1.18)", async (source, path, body, typed) => {
    post.mockResolvedValue({});
    render(<ImportSources orgId="org-1" onImported={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("documents.import_source"), source);
    await userEvent.type(screen.getByLabelText("documents.import_target"), typed);
    await userEvent.click(screen.getByRole("button", { name: "documents.import_button" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith(`/organizations/org-1/${path}`, body));
  });

  it("sends the user to Connected accounts when the organization has not connected the service", async () => {
    post.mockImplementationOnce(() => Promise.reject(new ApiError(403, "This organization has not connected notion. Add its credentials first")));
    render(<ImportSources orgId="org-1" onImported={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("documents.import_target"), "abc");
    await userEvent.click(screen.getByRole("button", { name: "documents.import_button" }));
    const link = await screen.findByRole("link", { name: "documents.import_connect_link" });
    expect(link).toHaveAttribute("href", "/dashboard/settings/connectors");
    expect(screen.getByRole("alert")).toHaveTextContent("documents.import_not_connected");
  });

  it("disables the button while the field is empty", () => {
    render(<ImportSources orgId="org-1" onImported={vi.fn()} />);
    expect(screen.getByRole("button", { name: "documents.import_button" })).toBeDisabled();
  });
});
