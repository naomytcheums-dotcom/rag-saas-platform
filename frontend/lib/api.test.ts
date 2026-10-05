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
});
