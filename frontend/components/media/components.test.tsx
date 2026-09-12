// Partie 22 -- real render/interaction tests for the media components.
// `@/lib/api` is mocked (no real network call in a component test) --
// same convention as ab-tests/analytics/plugins/whitelabel:
// tests/frontend/media/ (this part's own literal spec suggestion)
// sits outside vitest's project root and would never actually run.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DescriptionViewer } from "./DescriptionViewer";
import { MediaCard } from "./MediaCard";
import { MediaStatusBadge } from "./MediaStatusBadge";
import { VisualSearch } from "./VisualSearch";
import type { MediaAsset } from "@/lib/services/media";

// vi.mock's factory is hoisted above regular top-level statements --
// vi.hoisted lets `mockApi` exist before that hoisted call runs, so
// the factory can safely reference it (a plain top-level const here
// would throw "Cannot access before initialization").
const mockApi = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), postMultipart: vi.fn(), putMultipart: vi.fn(), postFile: vi.fn() }));

vi.mock("@/lib/api", () => ({
  api: mockApi,
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, detail: unknown) {
      super(String(detail));
      this.status = status;
    }
  },
  fileUrl: (path: string) => `http://localhost:8000${path}`,
}));

const BASE_ASSET: MediaAsset = {
  id: "11111111-1111-1111-1111-111111111111", organization_id: "org-1", uploaded_by: null,
  media_type: "image", status: "completed", filename: "photo.png", file_size: 2048, mime_type: "image/png",
  duration_ms: null, description: "Une photo de test.", ocr_text: null, objects_json: ["chaise"], tags_json: null,
  error: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};

describe("MediaStatusBadge", () => {
  it("renders the real status text", () => {
    render(<MediaStatusBadge status="processing" />);
    expect(screen.getByText("processing")).toBeInTheDocument();
  });
});

describe("MediaCard", () => {
  it("shows the filename, status, and description", () => {
    render(<MediaCard asset={BASE_ASSET} />);
    expect(screen.getByText(/photo\.png/)).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("Une photo de test.")).toBeInTheDocument();
  });

  it("shows the real duration for audio/video assets", () => {
    render(<MediaCard asset={{ ...BASE_ASSET, media_type: "video", duration_ms: 4200 }} />);
    expect(screen.getByText("4s")).toBeInTheDocument();
  });
});

describe("DescriptionViewer", () => {
  it("renders the real description, objects, and OCR text", () => {
    render(<DescriptionViewer asset={{ ...BASE_ASSET, ocr_text: "Texte OCR reel" }} />);
    expect(screen.getByText("Une photo de test.")).toBeInTheDocument();
    expect(screen.getByText("chaise")).toBeInTheDocument();
    expect(screen.getByText("Texte OCR reel")).toBeInTheDocument();
  });

  it("shows a real, honest empty state when nothing has been extracted yet", () => {
    render(<DescriptionViewer asset={{ ...BASE_ASSET, description: null, ocr_text: null, objects_json: null }} />);
    expect(screen.getByText("No description yet.")).toBeInTheDocument();
  });
});

describe("VisualSearch", () => {
  it("runs a real text-to-image (CLIP) search and renders ranked results", async () => {
    mockApi.post.mockResolvedValueOnce({ results: [{ media_asset_id: "a1", filename: "bus.jpg", score: 0.91 }] });
    render(<VisualSearch />);

    await userEvent.type(screen.getByPlaceholderText(/Describe what the image should show/i), "a photo of a bus");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(screen.getByText("bus.jpg")).toBeInTheDocument());
    expect(mockApi.post).toHaveBeenCalledWith("/media/search/visual", { query: "a photo of a bus", top_k: 10 });
    expect(screen.getByText("91% similar")).toBeInTheDocument();
  });

  it("runs a real image-to-image (CLIP) search on file upload", async () => {
    mockApi.postFile.mockResolvedValueOnce({ results: [{ media_asset_id: "a2", filename: "similar.jpg", score: 0.8 }] });
    render(<VisualSearch />);

    const file = new File(["fake-bytes"], "query.png", { type: "image/png" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, file);

    await waitFor(() => expect(screen.getByText("similar.jpg")).toBeInTheDocument());
    expect(mockApi.postFile).toHaveBeenCalledWith("/media/search/similar", file);
  });
});
