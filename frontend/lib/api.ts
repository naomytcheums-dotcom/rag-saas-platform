// Thin, real fetch wrapper for the FastAPI backend (api/main.py).
// NEXT_PUBLIC_API_URL points at that real backend's own origin (see
// .env.local.example) -- never hardcoded, so this frontend can point
// at a local dev server, staging, or production without a code change.

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed with status ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("access_token");
}

function setAccessToken(token: string) {
  window.localStorage.setItem("access_token", token);
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

// Real "stay signed in" mechanism: the backend already issues a real,
// httpOnly refresh-token cookie good for REFRESH_TOKEN_EXPIRE_DAYS (30
// days, api/config.py) whenever a user logs in -- the real gap was
// never a missing "remember me" feature, it was that this frontend
// never actually called POST /auth/refresh when the short-lived (15
// minute) access token expired, so every real session silently died
// after 15 minutes of use no matter what. This single in-flight
// promise is shared across concurrent 401s so a page firing several
// requests at once triggers exactly one real refresh call, not one
// per request.
let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const csrfToken = getCookie("csrf_token");
        const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: "POST",
          headers: csrfToken ? { "X-CSRF-Token": csrfToken } : undefined,
          credentials: "include",
        });
        if (!response.ok) return false;
        const data = (await response.json()) as { access_token: string };
        setAccessToken(data.access_token);
        return true;
      } catch {
        return false;
      } finally {
        refreshPromise = null;
      }
    })();
  }
  return refreshPromise;
}

async function parseErrorDetail(response: Response): Promise<unknown> {
  try {
    return (await response.json()).detail;
  } catch {
    return response.text();
  }
}

async function request<T>(path: string, init?: RequestInit, _retried = false): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type") && init?.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, credentials: "include" });

  if (response.status === 401 && !_retried && path !== "/auth/refresh" && path !== "/auth/login") {
    if (await refreshAccessToken()) return request<T>(path, init, true);
  }

  if (!response.ok) throw new ApiError(response.status, await parseErrorDetail(response));

  if (response.status === 204) return undefined as T;

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) return (await response.json()) as T;
  return (await response.text()) as unknown as T;
}

async function requestForm<T>(path: string, method: string, file: File, _retried = false): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const form = new FormData();
  form.set("file", file);

  const response = await fetch(`${API_BASE_URL}${path}`, { method, headers, body: form, credentials: "include" });

  if (response.status === 401 && !_retried) {
    if (await refreshAccessToken()) return requestForm<T>(path, method, file, true);
  }

  if (!response.ok) throw new ApiError(response.status, await parseErrorDetail(response));
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  postFile: <T>(path: string, file: File) => requestForm<T>(path, "POST", file),
};

export function fileUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}
