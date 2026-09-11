import { resolveApiUrl } from "../utils/resolveBackendUrl";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../lib/enforcerNativeCmd";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";

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

function lifeTransport(): "gateway" | "http" {
  if (!isFocusDesktopShell()) return "http";
  if (!isFocusEnforcerBridgeAvailable()) throw new Error("enforcer_unreachable");
  return "gateway";
}

async function lifeGateway(
  op: string,
  payload: Record<string, unknown> = {},
  timeoutMs = 8000,
): Promise<Record<string, unknown>> {
  const res = await enforcerNativeCmd(op, payload, timeoutMs);
  if (!res) throw new Error("enforcer_unreachable");
  if (res.ok === false) throw new Error(String(res.error || "enforcer_cmd_failed"));
  return res as Record<string, unknown>;
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

export interface JournalLogEntry {
  id: number;
  entry_date: string;
  title?: string | null;
  updated_at?: string | null;
  content_length: number;
  word_count: number;
}

export async function fetchJournalSummary(day?: string): Promise<JournalSummary> {
  if (lifeTransport() === "gateway") {
    const res = await lifeGateway("journal.summary", { day: day || "" });
    return (res.summary as JournalSummary) || {
      day: day || "",
      journal_written: false,
      journal_entry: null,
    };
  }
  const qs = day ? `?day=${day}` : "";
  const r = await fetch(resolveApiUrl(`/api/journal/summary${qs}`), { headers: authHeaders() });
  if (!r.ok) throw new Error(await apiError(r));
  return r.json();
}

export async function saveJournalEntry(body: {
  content: string;
  title?: string;
  entry_date?: string;
}): Promise<JournalEntry> {
  if (lifeTransport() === "gateway") {
    const res = await lifeGateway("journal.upsert", { ...body });
    return res.entry as JournalEntry;
  }
  const r = await fetch(resolveApiUrl("/api/journal/entries"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await apiError(r));
  const data = (await r.json()) as { entry: JournalEntry };
  return data.entry;
}

export async function fetchJournalLog(limit = 30): Promise<JournalLogEntry[]> {
  if (lifeTransport() === "gateway") {
    const res = await lifeGateway("journal.log", { limit });
    return (res.entries as JournalLogEntry[]) || [];
  }
  const params = new URLSearchParams({ limit: String(limit) });
  const r = await fetch(resolveApiUrl(`/api/journal/entries/log?${params}`), {
    headers: authHeaders(),
  });
  if (r.status === 404 || r.status === 405) return [];
  if (!r.ok) throw new Error(await apiError(r));
  const data = (await r.json()) as { entries: JournalLogEntry[] };
  return data.entries;
}
