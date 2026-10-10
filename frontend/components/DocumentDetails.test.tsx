// Specs 2.2.4 / 2.2.6 / 2.2.7 / 2.2.8 / 2.2.9 / 2.2.10 / 2.2.12: the per-document panel (tags, versions, history, re-index, duplicates, replace, preview).
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const del = vi.fn();
const postFile = vi.fn();

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
  return {
    api: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a), delete: (...a: unknown[]) => del(...a), postFile: (...a: unknown[]) => postFile(...a) },
    ApiError,
    fileUrl: (p: string) => `http://api.test${p}`,
  };
});

import { ApiError } from "@/lib/api";
import DocumentDetails from "./DocumentDetails";

const tagA = { id: "t1", name: "Legal", color: null };
const tagB = { id: "t2", name: "HR", color: null };

beforeEach(() => {
  get.mockReset(); post.mockReset(); del.mockReset(); postFile.mockReset();
  get.mockImplementation((path: string) => {
    if (path === "/organizations/org-1/tags") return Promise.resolve([tagA, tagB]);
    if (path === "/documents/d1/tags") return Promise.resolve([tagA]);
    if (path === "/documents/d1/versions") return Promise.resolve([{ id: "v1", version_number: 2, file_size: 5, created_at: "2026-10-10T10:00:00Z" }]);
    if (path === "/documents/d1/history") return Promise.resolve([{ id: "h1", action: "reindexed", timestamp: "2026-10-10T11:00:00Z" }]);
    if (path === "/documents/d1/duplicates") return Promise.resolve([{ id: "d2", name: "copy.pdf" }]);
    return Promise.resolve([]);
  });
  post.mockResolvedValue({});
  del.mockResolvedValue({});
  postFile.mockResolvedValue({});
});

const renderPanel = () => render(<DocumentDetails documentId="d1" orgId="org-1" onChanged={vi.fn()} />);

describe("DocumentDetails", () => {
  it("shows tags, versions and history", async () => {
    renderPanel();
    expect(await screen.findByText("Legal")).toBeInTheDocument();
    expect(screen.getByText(/v2 ·/)).toBeInTheDocument();
    expect(screen.getByText(/reindexed ·/)).toBeInTheDocument();
  });

  it("assigns an existing tag, only offering the tags not yet on the document", async () => {
    renderPanel();
    const select = await screen.findByLabelText("documents.add_tag");
    expect(screen.queryByRole("option", { name: "Legal" })).toBeNull();
    await userEvent.selectOptions(select, "t2");
    await waitFor(() => expect(post).toHaveBeenCalledWith("/documents/d1/tags", { tag_id: "t2" }));
  });

  it("removes a tag", async () => {
    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "documents.remove_tag Legal" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/documents/d1/tags/t1"));
  });

  it("creates a tag and assigns it", async () => {
    post.mockImplementation((path: string) => Promise.resolve(path === "/organizations/org-1/tags" ? { id: "t3", name: "Finance", color: null } : {}));
    renderPanel();
    await userEvent.type(await screen.findByLabelText("documents.new_tag"), "Finance");
    await userEvent.click(screen.getByRole("button", { name: "documents.create_tag" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/organizations/org-1/tags", { name: "Finance" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/documents/d1/tags", { tag_id: "t3" }));
  });

  it("schedules a re-index and reports it", async () => {
    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "documents.reindex" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/documents/d1/reindex"));
    expect(await screen.findByRole("status")).toHaveTextContent("documents.reindex_scheduled");
  });

  it("lists duplicates", async () => {
    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "documents.find_duplicates" }));
    expect(await screen.findByText(/copy\.pdf/)).toBeInTheDocument();
  });

  it("shows the server error when an action fails", async () => {
    post.mockRejectedValue(new ApiError(403, "You can only reindex a document you uploaded yourself"));
    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "documents.reindex" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("You can only reindex");
  });
});
