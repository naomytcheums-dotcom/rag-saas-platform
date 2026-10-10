// Turns an API error `detail` into text a person can read. FastAPI answers a validation failure (422) with an ARRAY of
// {loc, msg, ...} objects: String(detail) on it prints "[object Object]". A plain string is returned unchanged.

export function describeApiDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const { loc, msg } = item as { loc?: unknown; msg?: unknown };
          if (typeof msg !== "string" || !msg) return "";
          const field = Array.isArray(loc) ? loc.filter((part) => part !== "body").join(".") : "";
          return field ? `${field}: ${msg}` : msg;
        }
        return "";
      })
      .filter(Boolean);
    if (parts.length > 0) return parts.join("; ");
  }
  return fallback;
}
