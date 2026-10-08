import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

describe("cookie-authenticated requests", () => {
  beforeEach(() => {
    document.cookie = "csrf_token=browser-csrf; path=/";
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", {
      headers: { "Content-Type": "application/json" },
    })));
  });

  afterEach(() => {
    document.cookie = "csrf_token=; max-age=0; path=/";
    vi.unstubAllGlobals();
  });

  it.each(["/auth/logout", "/auth/refresh"])("echoes the CSRF cookie for %s", async (path) => {
    await api.post(path);
    const options = vi.mocked(fetch).mock.calls[0][1];
    expect(new Headers(options?.headers).get("X-CSRF-Token")).toBe("browser-csrf");
    expect(options?.credentials).toBe("include");
  });

  it("does not send the CSRF token to unrelated routes", async () => {
    await api.post("/organizations", { name: "Test" });
    expect(new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers).has("X-CSRF-Token")).toBe(false);
  });

  it("does not invent a CSRF token when the cookie is missing", async () => {
    document.cookie = "csrf_token=; max-age=0; path=/";
    await api.post("/auth/logout");
    expect(new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers).has("X-CSRF-Token")).toBe(false);
  });

  it("refreshes an expired session before retrying a raw streaming request", async () => {
    localStorage.setItem("access_token", "expired-token");
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: "refreshed-token" }), {
        headers: { "Content-Type": "application/json" },
      }))
      .mockResolvedValueOnce(new Response("event: done\n\n", { status: 200 }));

    const response = await api.fetchRaw("/chat/stream", { method: "POST", body: "{}" });

    expect(response.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get("Authorization")).toBe("Bearer expired-token");
    expect(String(fetchMock.mock.calls[1][0])).toContain("/auth/refresh");
    expect(new Headers(fetchMock.mock.calls[2][1]?.headers).get("Authorization")).toBe("Bearer refreshed-token");
    expect(localStorage.getItem("access_token")).toBe("refreshed-token");
  });
});
