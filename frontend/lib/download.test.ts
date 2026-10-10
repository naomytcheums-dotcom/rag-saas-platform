// Protected downloads must carry the bearer token (a plain link answers 401).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
  return { ApiError, fileUrl: (p: string) => `http://api.test${p}` };
});

import { downloadWithAuth } from "./download";

const fetchMock = vi.fn();
let clicked: HTMLAnchorElement | null = null;

beforeEach(() => {
  fetchMock.mockReset();
  clicked = null;
  vi.stubGlobal("fetch", fetchMock);
  window.localStorage.setItem("access_token", "tok-1");
  URL.createObjectURL = vi.fn(() => "blob:abc");
  URL.revokeObjectURL = vi.fn();
  // eslint-disable-next-line @typescript-eslint/no-this-alias -- the spy must capture the clicked anchor
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { clicked = this; });
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("downloadWithAuth", () => {
  it("sends the bearer token and saves the file under the requested name", async () => {
    fetchMock.mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(["data"])) });
    await downloadWithAuth("/compliance/data-export?fmt=json", "my-data.json");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/compliance/data-export?fmt=json");
    expect(init.headers).toEqual({ Authorization: "Bearer tok-1" });
    expect(clicked?.download).toBe("my-data.json");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:abc");
  });

  it("sends no Authorization header when there is no session", async () => {
    window.localStorage.clear();
    fetchMock.mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(["x"])) });
    await downloadWithAuth("/x", "x.txt");
    expect(fetchMock.mock.calls[0][1].headers).toEqual({});
  });

  it("throws the API error and saves nothing when the server refuses", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 401, text: () => Promise.resolve("Unauthorized") });
    await expect(downloadWithAuth("/x", "x.txt")).rejects.toMatchObject({ status: 401 });
    expect(clicked).toBeNull();
  });
});
