import { resolveApiUrl } from "../utils/resolveBackendUrl";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../lib/enforcerNativeCmd";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";
import { readFocusBibleChapter } from "../utils/bibleCorpus";

const TOKEN_KEY = "vocab:auth-token";

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) headers.Authorization = `Bearer ${token}`;
  } catch {
    /* ignore */
  }
  return headers;
}

function lifeTransport(): "gateway" | "http" {
  if (!isFocusDesktopShell()) return "http";
  if (!isFocusEnforcerBridgeAvailable()) throw new Error("enforcer_unreachable");
  return "gateway";
}

async function lifeGateway(
  op: string,
  payload: Record<string, unknown> = {},
  timeoutMs = 12000,
): Promise<Record<string, unknown>> {
  const res = await enforcerNativeCmd(op, payload, timeoutMs);
  if (!res) throw new Error("enforcer_unreachable");
  if (res.ok === false) throw new Error(String(res.error || "enforcer_cmd_failed"));
  return res as Record<string, unknown>;
}

export type BibleBookmark = {
  id: number;
  page: number;
  label: string;
  created_at?: string;
};

export type ChapterGoal = {
  done: number;
  target: number;
  met: boolean;
};

export type TodayChapter = {
  book: string;
  chapter: number;
  key: string;
  label: string;
  done: boolean;
  mode?: string;
};

export type BibleState = {
  day: string;
  bible_minutes: number;
  bible_seconds: number;
  game_bank_remaining_minutes: number;
  game_bank_remaining_seconds: number;
  last_page: number;
  last_book?: string;
  last_chapter?: number;
  last_verse?: number;
  next_bank_in_minutes?: number;
  today_chapter?: TodayChapter;
  chapters_completed_today?: string[];
  chapter_goal?: ChapterGoal;
  completed_chapters?: string[];
  bookmarks: BibleBookmark[];
  gate?: Record<string, unknown>;
};

export type BibleBookMeta = {
  id: string;
  name: string;
  testament: string;
  num_chapters: number;
};

export type BibleMeta = {
  version: string;
  version_name: string;
  license: string;
  book_count: number;
  books: BibleBookMeta[];
};

export type BibleVerse = { number: number; text: string };

export type BibleChapter = {
  version: string;
  version_name: string;
  name: string;
  book_id: string;
  testament: string;
  num_chapters: number;
  chapter: number;
  verses: BibleVerse[];
};

export async function fetchBibleState(): Promise<BibleState> {
  if (lifeTransport() === "gateway") {
    const res = await lifeGateway("bible.state");
    return (res.state as BibleState) || ({} as BibleState);
  }
  const r = await fetch(resolveApiUrl("/api/bible/state"), { headers: authHeaders() });
  if (!r.ok) throw new Error(`bible/state: ${r.status}`);
  return r.json();
}

export async function fetchBibleToday(version = "web"): Promise<
  BibleState & {
    today_chapter: TodayChapter;
    chapter: BibleChapter;
    preview_verses?: BibleVerse[];
  }
> {
  if (lifeTransport() === "gateway") {
    const res = await lifeGateway("bible.today", { version });
    const state = (res.state as BibleState) || ({} as BibleState);
    const tc = state.today_chapter as TodayChapter;
    const chapter =
      (await readFocusBibleChapter(tc?.book || "Genesis", tc?.chapter || 1)) ||
      ({
        version: "web",
        version_name: "World English Bible",
        name: tc?.book || "Genesis",
        book_id: "genesis",
        testament: "",
        num_chapters: 1,
        chapter: tc?.chapter || 1,
        verses: [],
      } as BibleChapter);
    return { ...state, today_chapter: tc, chapter, preview_verses: chapter.verses?.slice(0, 3) };
  }
  const r = await fetch(
    resolveApiUrl(`/api/bible/v2/today?version=${encodeURIComponent(version)}`),
    { headers: authHeaders() },
  );
  if (!r.ok) throw new Error(`bible/v2/today: ${r.status}`);
  return r.json();
}

export async function fetchBibleMeta(version = "web"): Promise<BibleMeta> {
  if (lifeTransport() === "gateway") {
    // Meta from corpus not required for devotion UI — soft empty
    return {
      version: "web",
      version_name: "World English Bible",
      license: "",
      book_count: 0,
      books: [],
    };
  }
  const r = await fetch(resolveApiUrl(`/api/bible/v2/meta?version=${encodeURIComponent(version)}`), {
    headers: authHeaders(),
  });
  if (!r.ok) throw new Error(`bible/v2/meta: ${r.status}`);
  return r.json();
}

export async function fetchBibleChapter(
  book: string,
  chapter: number,
  version = "web",
): Promise<BibleChapter> {
  if (lifeTransport() === "gateway") {
    const ch = await readFocusBibleChapter(book, chapter);
    if (!ch) throw new Error("bible chapter missing (calt-bible corpus)");
    return ch;
  }
  const r = await fetch(
    resolveApiUrl(
      `/api/bible/v2/read/${encodeURIComponent(version)}/${encodeURIComponent(book)}/${chapter}`,
    ),
    { headers: authHeaders() },
  );
  if (!r.ok) throw new Error(`bible/v2/read: ${r.status}`);
  return r.json();
}

export async function bibleChapterHeartbeat(
  book: string,
  chapter: number,
  focused: boolean,
  verse = 1,
): Promise<BibleState> {
  if (lifeTransport() === "gateway") {
    const res = await lifeGateway("bible.heartbeat", { book, chapter, focused, verse });
    return (res.state as BibleState) || ({} as BibleState);
  }
  const r = await fetch(resolveApiUrl("/api/bible/v2/heartbeat"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ book, chapter, verse, focused }),
  });
  if (!r.ok) throw new Error(`bible/v2/heartbeat: ${r.status}`);
  return r.json();
}

export async function tickBibleChapter(
  book: string,
  chapter: number,
  done = true,
): Promise<BibleState & { key?: string; done?: boolean }> {
  if (lifeTransport() === "gateway") {
    const res = await lifeGateway("bible.tick", { book, chapter, done });
    return (res.state as BibleState & { key?: string; done?: boolean }) || ({} as BibleState);
  }
  const r = await fetch(resolveApiUrl("/api/bible/v2/chapters/tick"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ book, chapter, done }),
  });
  if (!r.ok) throw new Error(`bible/v2/chapters/tick: ${r.status}`);
  return r.json();
}

/** @deprecated PDF heartbeat — prefer bibleChapterHeartbeat */
export async function bibleHeartbeat(page: number, focused: boolean): Promise<BibleState> {
  const res = await fetch(resolveApiUrl("/api/bible/heartbeat"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ page, focused }),
  });
  if (!res.ok) throw new Error(`bible/heartbeat: ${res.status}`);
  return res.json();
}

export async function addBibleBookmark(page: number, label: string): Promise<BibleBookmark> {
  const res = await fetch(resolveApiUrl("/api/bible/bookmarks"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ page, label }),
  });
  if (!res.ok) throw new Error(`bible/bookmarks: ${res.status}`);
  return res.json();
}

export async function deleteBibleBookmark(id: number): Promise<void> {
  const res = await fetch(resolveApiUrl(`/api/bible/bookmarks/${id}`), {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`bible/bookmarks delete: ${res.status}`);
}

export function biblePdfUrl(): string {
  const base = resolveApiUrl("/api/bible/pdf").replace(/\/$/, "");
  let token = "";
  try {
    token = localStorage.getItem(TOKEN_KEY) || "";
  } catch {
    /* ignore */
  }
  return token ? `${base}?access_token=${encodeURIComponent(token)}` : base;
}

export async function fetchBiblePdfBlobUrl(): Promise<string> {
  const res = await fetch(resolveApiUrl("/api/bible/pdf"), { headers: authHeaders() });
  if (!res.ok) throw new Error(`bible/pdf: ${res.status}`);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export type DayPassStatus = {
  week_start: string;
  limit: number;
  used: number;
  remaining: number;
  already_active_today: boolean;
  confirm_phrase: string;
};

export async function fetchDayPassStatus(): Promise<DayPassStatus> {
  const res = await fetch(resolveApiUrl("/api/bible/day-pass"), { headers: authHeaders() });
  if (!res.ok) throw new Error(`bible/day-pass: ${res.status}`);
  return res.json();
}

export async function requestBibleDayPass(confirm: string): Promise<{
  ok?: boolean;
  message?: string;
  day_pass?: boolean;
  day_pass_status?: DayPassStatus;
  gate?: Record<string, unknown>;
}> {
  const res = await fetch(resolveApiUrl("/api/bible/day-pass"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ confirm }),
  });
  if (!res.ok) {
    let detail = `bible/day-pass: ${res.status}`;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function requestRewardDay(confirm: string): Promise<{
  ok?: boolean;
  message?: string;
  available?: number;
  active_today?: boolean;
  gate?: Record<string, unknown>;
}> {
  const res = await fetch(resolveApiUrl("/api/bible/reward-day"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ confirm }),
  });
  if (!res.ok) {
    let detail = `bible/reward-day: ${res.status}`;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export function chapterKey(book: string, chapter: number): string {
  return `${book}|${chapter}`;
}

export type DevotionSlot = "morning" | "afternoon" | "evening";

export type DevotionSlotInfo = {
  slot: DevotionSlot;
  note: string;
  done?: boolean;
  notes?: string;
  lords_prayer?: string;
  prayer?: string;
  book?: string;
  chapter?: number;
  key?: string;
  label?: string;
  worship_title?: string;
  worship_opening?: string;
  worship_theme?: string;
  hymn_id?: string;
};

export type DevotionTodayPayload = {
  morning: DevotionSlotInfo;
  afternoon: DevotionSlotInfo;
  evening: DevotionSlotInfo;
  today_chapter: TodayChapter;
  morning_chapter: BibleChapter;
  afternoon_chapter: BibleChapter | null;
  evening_chapter: BibleChapter | null;
  chapter_goal?: ChapterGoal;
  gate?: Record<string, unknown>;
  hymns_catalog?: { id: string; title: string; theme: string }[];
};

export async function fetchDevotionToday(version = "web"): Promise<DevotionTodayPayload> {
  if (lifeTransport() === "gateway") {
    const res = await lifeGateway("bible.devotion.today", { version });
    const d = (res.devotion as DevotionTodayPayload) || ({} as DevotionTodayPayload);
    const tc = d.today_chapter;
    if (tc?.book && tc?.chapter) {
      d.morning_chapter = await readFocusBibleChapter(tc.book, tc.chapter);
    }
    if (d.afternoon?.book && d.afternoon?.chapter) {
      d.afternoon_chapter = await readFocusBibleChapter(d.afternoon.book, d.afternoon.chapter);
    }
    if (d.evening?.book && d.evening?.chapter) {
      d.evening_chapter = await readFocusBibleChapter(d.evening.book, d.evening.chapter);
    }
    return d;
  }
  const r = await fetch(
    resolveApiUrl(`/api/bible/devotion/today?version=${encodeURIComponent(version)}`),
    { headers: authHeaders() },
  );
  if (!r.ok) throw new Error(`bible/devotion/today: ${r.status}`);
  return r.json();
}

export async function markDevotionDone(
  slot: DevotionSlot,
  done = true,
): Promise<DevotionTodayPayload | BibleState> {
  if (lifeTransport() === "gateway") {
    const res = await lifeGateway("bible.devotion.done", { slot, done });
    return (res.devotion as DevotionTodayPayload) || ({} as DevotionTodayPayload);
  }
  const r = await fetch(resolveApiUrl(`/api/bible/devotion/${slot}/done`), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ done }),
  });
  if (!r.ok) throw new Error(`bible/devotion/${slot}/done: ${r.status}`);
  return r.json();
}

export async function saveDevotionNotes(
  slot: DevotionSlot,
  notes: string,
): Promise<DevotionTodayPayload> {
  if (lifeTransport() === "gateway") {
    const res = await lifeGateway("bible.devotion.notes", { slot, notes });
    return (res.devotion as DevotionTodayPayload) || ({} as DevotionTodayPayload);
  }
  const r = await fetch(resolveApiUrl("/api/bible/devotion/notes"), {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ slot, notes }),
  });
  if (!r.ok) throw new Error(`bible/devotion/notes: ${r.status}`);
  return r.json();
}
