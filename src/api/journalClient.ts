import { resolveApiUrl } from "../utils/resolveBackendUrl";

const TOKEN_KEY = "vocab:auth-token";

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function apiError(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const data = JSON.parse(text) as { detail?: string; error?: { message?: string } };
    if (typeof data.detail === "string") return data.detail;
    if (data.error?.message) return data.error.message;
  } catch {
    /* plain text */
  }
  return text || res.statusText || "Request failed";
}

export interface JournalEntry {
  id: number;
  entry_date: string;
  title?: string | null;
  content: string;
  updated_at?: string | null;
}

export interface JournalSummary {
  day: string;
  journal_written: boolean;
  journal_entry: JournalEntry | null;
}

export async function fetchJournalSummary(day?: string): Promise<JournalSummary> {
  const qs = day ? `?day=${day}` : "";
  const res = await fetch(resolveApiUrl(`/api/journal/summary${qs}`), { headers: authHeaders() });
  if (!res.ok) throw new Error(await apiError(res));
  return res.json();
}

export async function saveJournalEntry(body: {
  content: string;
  title?: string;
  entry_date?: string;
}): Promise<JournalEntry> {
  const res = await fetch(resolveApiUrl("/api/journal/entries"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await apiError(res));
  const data = (await res.json()) as { entry: JournalEntry };
  return data.entry;
}
