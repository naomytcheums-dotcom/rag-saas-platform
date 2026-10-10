import { ApiError, fileUrl } from "@/lib/api";

/** Downloads a protected API file (data export, audit export, conversation export). A plain `<a href>` cannot send the Authorization header, so a link to a
 * protected route answers 401: fetch it with the bearer token, then hand the blob to the browser. */
export async function downloadWithAuth(path: string, filename: string): Promise<void> {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("access_token") : null;
  const response = await fetch(fileUrl(path), { credentials: "include", headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!response.ok) throw new ApiError(response.status, await response.text());
  const blob = await response.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}
