export const V_API_BASE = "http://localhost:8000/api/vocab";

export async function authFetch(
  path: string,
  token: string | null,
  init?: RequestInit
) {
  const headers = new Headers(init?.headers || {});
  if (!(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${V_API_BASE}${path}`, { ...init, headers });
  const isCsv = res.headers.get("content-type")?.includes("text/csv");
  const data = isCsv ? null : await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as any)?.detail || `HTTP ${res.status}`);
  return { res, data };
}

