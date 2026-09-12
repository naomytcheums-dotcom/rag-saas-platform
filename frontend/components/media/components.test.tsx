// Partie 22 -- real render/interaction tests for the media components.
// `@/lib/api` is mocked (no real network call in a component test) --
// same convention as ab-tests/analytics/plugins/whitelabel:
// tests/frontend/media/ (this part's own literal spec suggestion)
// sits outside vitest's project root and would never actually run.

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DescriptionViewer } from "./DescriptionViewer";
import { MediaCard } from "./MediaCard";
import { MediaStatusBadge } from "./MediaStatusBadge";
import type { MediaAsset } from "@/lib/services/media";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), postMultipart: vi.fn(), putMultipart: vi.fn(), postFile: vi.fn() },
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
