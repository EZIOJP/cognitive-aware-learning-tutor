/**
 * Focus shell: load WEB chapter text from mapped data/bible (no Study :8000).
 * WebView2: https://calt-bible.app → data/bible
 * Design host :5180: /calt-bible/
 */
import { isFocusDesktopShell } from "./focusDesktopShell";
import type { BibleChapter, BibleVerse } from "../api/bibleClient";

type WebBook = {
  id?: string;
  name: string;
  testament?: string;
  num_chapters?: number;
  chapters?: Array<Array<{ number?: number; text?: string } | string>>;
};

type WebBible = {
  version?: string;
  versionName?: string;
  license?: string;
  books?: WebBook[];
};

let cache: WebBible | null = null;
let loadPromise: Promise<WebBible | null> | null = null;

export function focusBibleBaseUrl(): string {
  if (typeof window === "undefined") return "https://calt-bible.app";
  const h = window.location.hostname;
  const port = window.location.port;
  if ((h === "127.0.0.1" || h === "localhost") && (port === "5180" || port === "5174")) {
    return "/calt-bible";
  }
  return "https://calt-bible.app";
}

function slug(name: string): string {
  return (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

async function loadWeb(): Promise<WebBible | null> {
  if (cache) return cache;
  if (loadPromise) return loadPromise;
  loadPromise = (async () => {
    try {
      const r = await fetch(`${focusBibleBaseUrl()}/structured/web.json`, { cache: "force-cache" });
      if (!r.ok) return null;
      const j = (await r.json()) as WebBible;
      if (!j?.books?.length) return null;
      cache = j;
      return j;
    } catch {
      return null;
    } finally {
      loadPromise = null;
    }
  })();
  return loadPromise;
}

export async function readFocusBibleChapter(
  book: string,
  chapter: number,
): Promise<BibleChapter | null> {
  if (!isFocusDesktopShell()) return null;
  const data = await loadWeb();
  if (!data?.books) return null;
  const needle = slug(book);
  const b = data.books.find(
    (x) => slug(String(x.id || "")) === needle || slug(String(x.name || "")) === needle,
  );
  if (!b) return null;
  const chapters = b.chapters || [];
  const ch = Math.max(1, Math.floor(chapter));
  if (ch < 1 || ch > chapters.length) return null;
  const raw = chapters[ch - 1] || [];
  const verses: BibleVerse[] = raw.map((v, i) => {
    if (typeof v === "string") return { number: i + 1, text: v };
    return { number: Number(v.number || i + 1), text: String(v.text || "").trim() };
  });
  return {
    version: String(data.version || "web"),
    version_name: String(data.versionName || "World English Bible"),
    name: String(b.name),
    book_id: String(b.id || slug(b.name)),
    testament: String(b.testament || ""),
    num_chapters: chapters.length,
    chapter: ch,
    verses,
  };
}
