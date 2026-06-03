import { authFetch } from "../features/vocab/api/authClient";
import type { GroupSummary, QuizAttempt, QuizResults } from "../features/vocab/cycle/types";
import type { WordWithProgress } from "../features/vocab/types";

const TOKEN_KEY = "vocab:auth-token";

export function getVocabToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export class VocabApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "VocabApiError";
  }
}

async function vocabRequest<T>(
  path: string,
  init?: RequestInit,
  options?: { throwOnError?: boolean }
): Promise<T | null> {
  try {
    const { data } = await authFetch(path, getVocabToken(), init);
    return data as T;
  } catch (e) {
    if (options?.throwOnError) {
      throw new VocabApiError(e instanceof Error ? e.message : "Vocab API request failed");
    }
    return null;
  }
}

export type ReadListMode =
  | "all"
  | "low"
  | "struggling"
  | "learning"
  | "practicing"
  | "mastered"
  | "due";

function criteriaQueryForReadMode(
  mode: ReadListMode,
  groupNumber?: number | null
): string {
  const params = new URLSearchParams();
  params.set("limit", "2000");
  params.set("offset", "0");
  if (groupNumber != null) params.set("group", String(groupNumber));
  switch (mode) {
    case "low":
      params.set("mastery_max", "0");
      break;
    case "struggling":
      params.set("mastery_max", "-1");
      break;
    case "learning":
      params.set("mastery_min", "0");
      params.set("mastery_max", "2");
      break;
    case "practicing":
      params.set("mastery_min", "3");
      params.set("mastery_max", "5");
      break;
    case "mastered":
      params.set("mastery_min", String(6));
      break;
    case "due":
      params.set("due_for_review", "true");
      break;
    default:
      break;
  }
  return params.toString();
}

export async function fetchWordsForReadMode(
  mode: ReadListMode,
  groupNumber?: number | null
): Promise<WordWithProgress[] | null> {
  const q = criteriaQueryForReadMode(mode, groupNumber);
  const data = await vocabRequest<{ words: Record<string, unknown>[] }>(
    `/words/by-criteria/?${q}`
  );
  if (!data?.words) return null;
  return data.words.map(mapApiWord);
}

export async function recordWordReadApi(
  wordId: number
): Promise<{ mastery_after: number } | null> {
  return vocabRequest(`/progress/${wordId}/read`, { method: "POST" });
}

function mapApiWord(w: Record<string, unknown>): WordWithProgress {
  return {
    id: Number(w.id),
    word: String(w.word ?? ""),
    pronunciation: w.pronunciation ? String(w.pronunciation) : undefined,
    meaning: String(w.meaning ?? ""),
    connotation: w.connotation ? String(w.connotation) : undefined,
    group_number: Number(w.group_number ?? 1),
    story_mnemonic: w.story_mnemonic ? String(w.story_mnemonic) : undefined,
    etymology: w.etymology ? String(w.etymology) : undefined,
    synonyms: Array.isArray(w.synonyms) ? (w.synonyms as string[]) : undefined,
    examples: Array.isArray(w.examples)
      ? (w.examples as WordWithProgress["examples"])
      : undefined,
    mastery: Number(w.mastery ?? 0),
    times_asked: Number(w.times_asked ?? 0),
    times_correct: Number(w.times_correct ?? 0),
    consecutive_correct: Number(w.consecutive_correct ?? 0),
    accuracy_rate: Number(w.accuracy_rate ?? 0),
    is_due: Boolean(w.is_due),
  };
}

export async function fetchGroupsDetailedApi(): Promise<GroupSummary[] | null> {
  const data = await vocabRequest<{ groups: GroupSummary[] }>("/groups/detailed/");
  return data?.groups ?? null;
}

export type VocabProgressSummary = {
  studied_words: number;
  mastered_words: number;
  due_reviews: number;
  suspended_words: number;
  avg_accuracy: number;
  last_updated: string | null;
};

export async function fetchProgressSummary(): Promise<VocabProgressSummary | null> {
  return vocabRequest<VocabProgressSummary>("/progress/summary");
}

export type QuizDashboardPayload = {
  total_words: number;
  studied_words: number;
  mastered: number;
  due_reviews: { count: number };
  low_mastery: { count: number };
  overall_accuracy: number;
  study_coverage_pct: number;
};

export async function fetchQuizDashboard(): Promise<QuizDashboardPayload | null> {
  return vocabRequest<QuizDashboardPayload>("/quiz/dashboard/");
}

export async function fetchWordsByGroup(
  groupNumber: number
): Promise<WordWithProgress[] | null> {
  const data = await vocabRequest<{ words: Record<string, unknown>[] }>(
    `/words/by-criteria/?group=${groupNumber}&limit=500`
  );
  if (!data?.words) return null;
  return data.words.map(mapApiWord);
}

export type AdaptiveQuestion = {
  session_complete: boolean;
  word_id?: number;
  word?: string;
  pronunciation?: string;
  options?: string[];
  question_number?: number;
  total_questions?: number;
};

export async function startAdaptiveQuiz(body: {
  quiz_type?: string;
  group_number?: number;
  word_ids?: number[];
}): Promise<{ session_id: string; total_questions: number } | null> {
  return vocabRequest("/quiz/adaptive/start/", {
    method: "POST",
    body: JSON.stringify({
      quiz_type: body.quiz_type ?? "adaptive_group",
      group_number: body.group_number ?? null,
      word_ids: body.word_ids ?? [],
    }),
  });
}

export async function fetchAdaptiveQuestion(
  sessionId: string
): Promise<AdaptiveQuestion | null> {
  return vocabRequest(`/quiz/adaptive/${sessionId}/question/`);
}

export async function submitAdaptiveAnswer(
  sessionId: string,
  body: { word_id: number; answer: string; time_taken: number }
): Promise<{
  is_correct: boolean;
  correct_answer: string;
  mastery_before: number;
  mastery_after: number;
} | null> {
  return vocabRequest(`/quiz/adaptive/${sessionId}/answer/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function completeAdaptiveQuiz(
  sessionId: string
): Promise<QuizResults | null> {
  const data = await vocabRequest<{
    performance: QuizResults["performance"];
    attempts: Array<{
      word_id: number;
      word: string;
      is_correct: boolean;
      mastery_before: number;
      mastery_after: number;
    }>;
  }>(`/quiz/adaptive/${sessionId}/complete/`, { method: "POST" });
  if (!data) return null;
  return {
    session_id: sessionId,
    performance: data.performance,
    attempts: data.attempts.map((a) => ({
      word_id: a.word_id,
      word: a.word,
      user_answer: "",
      correct_answer: "",
      is_correct: a.is_correct,
      mastery_before: a.mastery_before,
      mastery_after: a.mastery_after,
      time_taken: 0,
    })),
  };
}

export function hasVocabApi(): boolean {
  return Boolean(getVocabToken());
}
