import { resolveApiUrl } from "../utils/resolveBackendUrl";

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
  const res = await fetch(resolveApiUrl("/api/bible/state"), { headers: authHeaders() });
  if (!res.ok) throw new Error(`bible/state: ${res.status}`);
  return res.json();
}

export async function fetchBibleToday(version = "web"): Promise<
  BibleState & {
    today_chapter: TodayChapter;
    chapter: BibleChapter;
    preview_verses?: BibleVerse[];
  }
> {
  const res = await fetch(
    resolveApiUrl(`/api/bible/v2/today?version=${encodeURIComponent(version)}`),
    { headers: authHeaders() },
  );
  if (!res.ok) throw new Error(`bible/v2/today: ${res.status}`);
  return res.json();
}

export async function fetchBibleMeta(version = "web"): Promise<BibleMeta> {
  const res = await fetch(resolveApiUrl(`/api/bible/v2/meta?version=${encodeURIComponent(version)}`), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`bible/v2/meta: ${res.status}`);
  return res.json();
}

export async function fetchBibleChapter(
  book: string,
  chapter: number,
  version = "web",
): Promise<BibleChapter> {
  const res = await fetch(
    resolveApiUrl(
      `/api/bible/v2/read/${encodeURIComponent(version)}/${encodeURIComponent(book)}/${chapter}`,
    ),
    { headers: authHeaders() },
  );
  if (!res.ok) throw new Error(`bible/v2/read: ${res.status}`);
  return res.json();
}

export async function bibleChapterHeartbeat(
  book: string,
  chapter: number,
  focused: boolean,
  verse = 1,
): Promise<BibleState> {
  const res = await fetch(resolveApiUrl("/api/bible/v2/heartbeat"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ book, chapter, verse, focused }),
  });
  if (!res.ok) throw new Error(`bible/v2/heartbeat: ${res.status}`);
  return res.json();
}

export async function tickBibleChapter(
  book: string,
  chapter: number,
  done = true,
): Promise<BibleState & { key?: string; done?: boolean }> {
  const res = await fetch(resolveApiUrl("/api/bible/v2/chapters/tick"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ book, chapter, done }),
  });
  if (!res.ok) throw new Error(`bible/v2/chapters/tick: ${res.status}`);
  return res.json();
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
