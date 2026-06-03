/**
 * Client-side vocab data — words.json + localStorage progress
 */
import type {
  VocabWord,
  WordProgress,
  WordWithProgress,
  WordCriteria,
} from "../types";

const PROGRESS_KEY = "vocab:user-progress";
const WORDS_URL = "/data/words.json";

let wordsCache: VocabWord[] | null = null;

export type ReadListMode =
  | "all"
  | "low"
  | "struggling"
  | "learning"
  | "practicing"
  | "mastered"
  | "due";

function loadProgressMap(): Record<number, WordProgress> {
  try {
    const raw = localStorage.getItem(PROGRESS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveProgressMap(map: Record<number, WordProgress>) {
  localStorage.setItem(PROGRESS_KEY, JSON.stringify(map));
}

function defaultProgress(): WordProgress {
  return {
    mastery: 0,
    times_asked: 0,
    times_correct: 0,
    consecutive_correct: 0,
    due_date: null,
    last_practiced: new Date().toISOString(),
    is_learning: true,
  };
}

function calcNextDueDate(mastery: number): string {
  const now = new Date();
  const days =
    mastery < 0 ? 1 : mastery <= 2 ? 2 : mastery <= 5 ? 7 : mastery <= 8 ? 21 : 60;
  now.setDate(now.getDate() + days);
  return now.toISOString();
}

function isDue(progress: WordProgress): boolean {
  if (!progress.due_date) return false;
  return new Date(progress.due_date) <= new Date();
}

export function mergeWord(
  word: VocabWord,
  progress?: WordProgress
): WordWithProgress {
  const p = progress ?? defaultProgress();
  const accuracy =
    p.times_asked > 0 ? (p.times_correct / p.times_asked) * 100 : 0;
  return {
    ...word,
    mastery: p.mastery,
    times_asked: p.times_asked,
    times_correct: p.times_correct,
    consecutive_correct: p.consecutive_correct,
    accuracy_rate: accuracy,
    is_due: isDue(p),
  };
}

export async function ensureWordsLoaded(): Promise<VocabWord[]> {
  if (wordsCache) return wordsCache;
  const res = await fetch(WORDS_URL);
  if (!res.ok) throw new Error(`Failed to load words (${res.status})`);
  const data = await res.json();
  const rawWords: VocabWord[] = Array.isArray(data) ? data : data.words ?? [];
  
  // Dynamically assign group numbers: 30 words per group
  wordsCache = rawWords.map((word, index) => ({
    ...word,
    group_number: Math.floor(index / 30) + 1,
  }));
  
  return wordsCache;
}

function matchesReadMode(word: WordWithProgress, mode: ReadListMode): boolean {
  const m = word.mastery;
  switch (mode) {
    case "all":
      return true;
    case "low":
      return m <= 0;
    case "struggling":
      return m < 0;
    case "learning":
      return m >= 0 && m <= 2;
    case "practicing":
      return m >= 3 && m <= 5;
    case "mastered":
      return m >= 6;
    case "due":
      return word.is_due;
    default:
      return true;
  }
}

/** Load full word list for read mode (no 30-word pagination cap). */
export async function loadWordsForRead(
  mode: ReadListMode,
  groupNumber?: number | null
): Promise<WordWithProgress[]> {
  const words = await ensureWordsLoaded();
  const progressMap = loadProgressMap();

  return words
    .map((w) => mergeWord(w, progressMap[w.id]))
    .filter((w) => matchesReadMode(w, mode))
    .filter((w) =>
      groupNumber == null ? true : w.group_number === groupNumber
    )
    .sort((a, b) => a.group_number - b.group_number || a.word.localeCompare(b.word));
}

export async function markWordRead(wordId: number): Promise<WordWithProgress> {
  const words = await ensureWordsLoaded();
  const word = words.find((w) => w.id === wordId);
  if (!word) throw new Error(`Word ${wordId} not found`);

  const progressMap = loadProgressMap();
  const p = progressMap[wordId] ?? defaultProgress();

  p.mastery += 1;
  p.times_asked += 1;
  p.times_correct += 1;
  p.consecutive_correct += 1;
  p.last_practiced = new Date().toISOString();
  p.is_learning = p.mastery < 6;

  if (p.mastery >= 3) {
    p.due_date = calcNextDueDate(p.mastery);
  }

  progressMap[wordId] = p;
  saveProgressMap(progressMap);

  return mergeWord(word, p);
}

export async function updateQuizAnswer(
  wordId: number,
  isCorrect: boolean
): Promise<WordWithProgress> {
  const words = await ensureWordsLoaded();
  const word = words.find((w) => w.id === wordId);
  if (!word) throw new Error(`Word ${wordId} not found`);

  const progressMap = loadProgressMap();
  const p = progressMap[wordId] ?? defaultProgress();

  if (isCorrect) {
    p.mastery += 1;
    p.times_correct += 1;
    p.consecutive_correct += 1;
  } else {
    p.mastery -= 2;
    p.consecutive_correct = 0;
  }
  p.times_asked += 1;
  p.last_practiced = new Date().toISOString();
  p.is_learning = p.mastery < 6;

  if (p.mastery >= 3 && isCorrect) {
    p.due_date = calcNextDueDate(p.mastery);
  }

  progressMap[wordId] = p;
  saveProgressMap(progressMap);

  return mergeWord(word, p);
}

export function clearAllProgress() {
  localStorage.removeItem(PROGRESS_KEY);
}

// Legacy paginated API (quiz / future modules)
function matchesCriteria(
  merged: WordWithProgress,
  criteria: WordCriteria
): boolean {
  if (criteria.group != null && merged.group_number !== Number(criteria.group)) {
    return false;
  }
  if (criteria.word_ids) {
    const ids = String(criteria.word_ids)
      .split(",")
      .map((s) => Number(s.trim()));
    if (!ids.includes(merged.id)) return false;
  }
  const min =
    criteria.mastery_min != null ? Number(criteria.mastery_min) : undefined;
  const max =
    criteria.mastery_max != null ? Number(criteria.mastery_max) : undefined;
  if (min != null && merged.mastery < min) return false;
  if (max != null && merged.mastery > max) return false;
  if (criteria.due_for_review === true || criteria.due_for_review === "true") {
    if (!merged.is_due) return false;
  }
  return true;
}

export async function queryWordsByCriteria(criteria: WordCriteria = {}) {
  const words = await ensureWordsLoaded();
  const progressMap = loadProgressMap();
  const limit = criteria.limit ?? 30;
  const offset = criteria.offset ?? 0;

  const merged = words
    .map((w) => mergeWord(w, progressMap[w.id]))
    .filter((w) => matchesCriteria(w, criteria));

  const page = merged.slice(offset, offset + limit);

  return {
    words: page,
    pagination: {
      limit,
      offset,
      returned: page.length,
      total_available: merged.length,
      has_more: offset + limit < merged.length,
    },
  };
}
