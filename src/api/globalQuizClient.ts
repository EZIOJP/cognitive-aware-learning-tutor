import { authFetch } from "../features/vocab/api/authClient";
import { getVocabToken } from "./vocabClient";
import type {
  CodeDrill,
  DueReviewItem,
  GlobalQuizAnswerResult,
  GlobalQuizQuestion,
  QuizBacklog,
  QuizDeckSummary,
  QuizDomain,
  QuizQuestion,
  QuizSessionSummary,
} from "../features/quiz/types";

async function quizRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const { data } = await authFetch(`/api/quiz${path}`, getVocabToken(), init);
  return data as T;
}

export async function fetchQuizBacklog(): Promise<QuizBacklog> {
  return quizRequest("/backlog");
}

export async function fetchQuizDecks(): Promise<{ decks: QuizDeckSummary[] }> {
  return quizRequest("/decks");
}

export async function saveQuizDeck(payload: {
  title: string;
  topic?: string;
  domain?: string;
  items: Array<Record<string, unknown>>;
  time_limit_sec?: number;
  deck_id?: number;
}): Promise<{ id: number; title: string; item_count: number; cards_seeded: number }> {
  return quizRequest("/decks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteQuizDeck(deckId: number): Promise<void> {
  await quizRequest(`/decks/${deckId}`, { method: "DELETE" });
}

export async function fetchRecentQuizResults(limit = 8): Promise<{
  results: Array<{
    session_id: string;
    domain: string;
    correct: number;
    total: number;
    accuracy_pct: number;
    completed_at?: string;
  }>;
}> {
  return quizRequest(`/results/recent?limit=${limit}`);
}

export async function startGlobalQuiz(
  domain: QuizDomain,
  config: Record<string, unknown>
): Promise<{ session_id: string; domain: string; question: GlobalQuizQuestion; card_count?: number }> {
  return quizRequest("/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ domain, config }),
  });
}

export async function startDeckQuiz(deckId: number): Promise<{
  session_id: string;
  domain: string;
  question: GlobalQuizQuestion;
}> {
  return startGlobalQuiz("deck", { deck_id: deckId });
}

export async function submitGlobalQuizAnswer(
  sessionId: string,
  payload: { item_id: string; response: string; time_taken_ms?: number }
): Promise<GlobalQuizAnswerResult> {
  return quizRequest(`/${sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      item_id: payload.item_id,
      response: payload.response,
      time_taken_ms: payload.time_taken_ms ?? 0,
    }),
  });
}

export async function completeGlobalQuiz(sessionId: string): Promise<QuizSessionSummary & { complete: boolean }> {
  return quizRequest(`/${sessionId}/complete`, { method: "POST" });
}

export async function fetchDueReview(limit = 40): Promise<{ items: DueReviewItem[]; count: number }> {
  return quizRequest(`/review/due?limit=${limit}`);
}

export function buildStudyQuizConfig(
  questions: QuizQuestion[],
  drills: CodeDrill[],
  notePath?: string,
  topic?: string,
  opts?: { time_limit_sec?: number; per_question_sec?: number }
): Record<string, unknown> {
  return {
    questions,
    drills,
    note_path: notePath ?? "",
    topic: topic ?? "",
    time_limit_sec: opts?.time_limit_sec,
    per_question_sec: opts?.per_question_sec,
  };
}

export function buildMathQuizConfig(
  topic: string,
  opts?: { time_limit_sec?: number }
): Record<string, unknown> {
  return { topic, time_limit_sec: opts?.time_limit_sec };
}
