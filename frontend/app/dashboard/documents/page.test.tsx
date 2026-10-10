// Spec 2.2.1 / 2.2.2 / 2.2.3: several files at once, drag and drop, and a list that keeps refreshing while documents are processed.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const postFile = vi.fn();

const translation = { t: (key: string) => key }; // stable identity, like the real context value (the page reloads when `t` changes)
vi.mock("@/lib/i18n", () => ({ useTranslation: () => translation }));
const currentOrg = { org: { id: "org-1" } }; // stable identity, like the real hook
vi.mock("@/lib/useCurrentOrg", () => ({ useCurrentOrg: () => currentOrg }));
vi.mock("@/components/LoadingState", () => ({ default: () => <p>loading</p> }));
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
  return { api: { get: (...a: unknown[]) => get(...a), postFile: (...a: unknown[]) => postFile(...a), delete: vi.fn() }, ApiError };
});

import { ApiError } from "@/lib/api";
import DocumentsPage from "./page";

const doc = (id: string, status: string) => ({ id, name: `${id}.pdf`, file_size: 10, file_type: "pdf", status });

beforeEach(() => {
  get.mockReset();
  postFile.mockReset();
});

describe("DocumentsPage", () => {
  it("uploads every dropped file, one request each", async () => {
    get.mockResolvedValue({ items: [] });
    postFile.mockResolvedValue({});
    render(<DocumentsPage />);
    await screen.findByText("documents.empty");
    const files = [new File(["a"], "a.txt"), new File(["b"], "b.txt")];
    fireEvent.drop(screen.getByTestId("drop-zone"), { dataTransfer: { files } });
    await waitFor(() => expect(postFile).toHaveBeenCalledTimes(2));
    expect(postFile).toHaveBeenNthCalledWith(1, "/organizations/org-1/documents", files[0]);
    expect(postFile).toHaveBeenNthCalledWith(2, "/organizations/org-1/documents", files[1]);
  });

  it("reports the failing file by name but still uploads the others", async () => {
    get.mockResolvedValue({ items: [] });
    postFile.mockRejectedValueOnce(new ApiError(415, "Unsupported type")).mockResolvedValueOnce({});
    render(<DocumentsPage />);
    await screen.findByText("documents.empty");
    fireEvent.drop(screen.getByTestId("drop-zone"), { dataTransfer: { files: [new File(["x"], "bad.exe"), new File(["y"], "ok.txt")] } });
    expect(await screen.findByText(/bad\.exe: Unsupported type/)).toBeInTheDocument();
    expect(postFile).toHaveBeenCalledTimes(2);
  });

  it("refreshes the list while a document is still being processed", async () => {
    get.mockResolvedValueOnce({ items: [doc("d1", "processing")] }).mockResolvedValue({ items: [doc("d1", "ready")] });
    render(<DocumentsPage />);
    await screen.findByText(/d1\.pdf/);
    expect(screen.getByText(/processing/)).toBeInTheDocument();
    // real timers: the page polls every 4 seconds while a document is not final
    expect(await screen.findByText(/ready/, {}, { timeout: 9000 })).toBeInTheDocument();
    expect(get.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
