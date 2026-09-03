import { getVocabToken } from "./vocabClient";
import { resolveApiUrl } from "../utils/resolveBackendUrl";
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

export class QuizApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail || `HTTP ${status}`);
    this.name = "QuizApiError";
    this.status = status;
    this.detail = detail || `HTTP ${status}`;
  }
}

function detailFromBody(data: unknown, status: number): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => JSON.stringify(x)).join("; ");
    if (d != null) return String(d);
  }
  return `HTTP ${status}`;
}

async function quizRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers || {});
  if (!(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getVocabToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${resolveApiUrl()}/api/quiz${path}`, { ...init, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new QuizApiError(res.status, detailFromBody(data, res.status));
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

export async function clearReviewCards(domain?: string): Promise<{ deleted: number }> {
  const q = domain ? `?domain=${encodeURIComponent(domain)}` : "";
  return quizRequest(`/review-cards${q}`, { method: "DELETE" });
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

export async function fetchGlobalQuizQuestion(
  sessionId: string
): Promise<{ question: GlobalQuizQuestion | null }> {
  return quizRequest(`/${sessionId}/question`);
}

export async function fetchDueReview(limit = 40): Promise<{ items: DueReviewItem[]; count: number }> {
  return quizRequest(`/review/due?limit=${limit}`);
}

export type ContentTopicSummary = {
  kind: string;
  topic_id: string;
  title: string;
  stage: string;
  track: string;
  path: string[];
  note_topic_ids: string[];
  description: string;
  question_count: number | null;
  source_file?: string;
  bank?: "curated" | "generator" | string;
  gen_id?: number;
};

export type GeneratorRecipeSummary = ContentTopicSummary & {
  gen_id: number;
  name?: string;
  subject?: string;
  source?: string;
};

export async function fetchContentCatalog(opts?: {
  kind?: string;
  track?: string;
  note_topic_id?: string;
}): Promise<{
  topics: ContentTopicSummary[];
  generators?: GeneratorRecipeSummary[];
  generator_count?: number;
  db_question_count?: number;
  hybrid?: boolean;
  kinds: Record<string, number>;
  topic_count: number;
  question_count: number;
  errors: Array<{ file?: string; error?: string }>;
  generator_error?: string | null;
}> {
  const q = new URLSearchParams();
  if (opts?.kind) q.set("kind", opts.kind);
  if (opts?.track) q.set("track", opts.track);
  if (opts?.note_topic_id) q.set("note_topic_id", opts.note_topic_id);
  const suffix = q.toString() ? `?${q}` : "";
  return quizRequest(`/content/catalog${suffix}`);
}

export async function fetchMathCurriculum(): Promise<{
  name?: string;
  levels: Array<{
    id: string;
    title: string;
    steps: Array<{
      order: number;
      note_topic_id: string;
      title: string;
      prefer_topic_ids: string[];
      optional?: boolean;
      notes_first?: boolean;
    }>;
  }>;
}> {
  return quizRequest("/content/curriculum");
}

export async function importContentBank(opts?: {
  kind?: string;
  topic_id?: string;
}): Promise<{ topics: number; cards_seeded: number; questions: number }> {
  const q = new URLSearchParams();
  if (opts?.kind) q.set("kind", opts.kind);
  if (opts?.topic_id) q.set("topic_id", opts.topic_id);
  const suffix = q.toString() ? `?${q}` : "";
  return quizRequest(`/content/import${suffix}`, { method: "POST" });
}

export async function syncContentBankToDb(kind = "math"): Promise<{
  inserted: number;
  updated: number;
  skipped: number;
  total_in_bank: number;
}> {
  return quizRequest(`/content/sync-db?kind=${encodeURIComponent(kind)}`, { method: "POST" });
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
  opts?: { time_limit_sec?: number; count?: number; node_id?: string; per_question_sec?: number }
): Record<string, unknown> {
  return {
    topic,
    count: opts?.count ?? 5,
    node_id: opts?.node_id,
    time_limit_sec: opts?.time_limit_sec,
    per_question_sec: opts?.per_question_sec,
  };
}

export type StudyLoopTag = {
  id: string;
  kind?: string;
  label?: string;
  question_count?: number;
  vocab_count?: number;
  has_read_card?: boolean;
  note_paths?: string[];
  due_count?: number;
  pillar_weight?: number;
  [key: string]: unknown;
};

export type StudyLoopReadCard = {
  card_id: string;
  tag?: string;
  title?: string;
  body_markdown?: string;
  heading_markdown?: string;
  note_path?: string;
  mtime?: number;
  source?: string;
  char_count?: number;
  [key: string]: unknown;
};

export async function fetchStudyLoopTags(opts?: { q?: string; kind?: string }) {
  const qs = new URLSearchParams();
  if (opts?.q) qs.set("q", opts.q);
  if (opts?.kind) qs.set("kind", opts.kind);
  const q = qs.toString();
  return quizRequest<{ tags: StudyLoopTag[]; count?: number }>(`/study-loop/tags${q ? `?${q}` : ""}`);
}

export async function fetchStudyLoopReadCards(tag: string) {
  return quizRequest<{ items: StudyLoopReadCard[]; count: number }>(
    `/study-loop/read-cards?tag=${encodeURIComponent(tag)}`
  );
}

export async function patchStudyLoopReadCard(
  cardId: string,
  body: { body_markdown: string; title?: string; expected_mtime?: number }
) {
  return quizRequest<StudyLoopReadCard>(`/study-loop/read-cards/${encodeURIComponent(cardId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function createStudyLoopSession(tag: string) {
  return quizRequest<{
    session_id: string;
    read_completed: boolean;
    tag: string;
    read_card_ids?: string[];
  }>(`/study-loop/sessions`, { method: "POST", body: JSON.stringify({ tag }) });
}

export async function markStudyLoopRead(sessionId: string) {
  return quizRequest(`/study-loop/sessions/${encodeURIComponent(sessionId)}/mark-read`, {
    method: "POST",
  });
}

export async function startStudyLoopPractice(sessionId: string, count = 5) {
  const raw = await quizRequest<{
    session_id: string;
    practice_quiz_session_id?: string | null;
    domain?: string;
    quiz?: { session_id?: string; domain?: string; question?: GlobalQuizQuestion };
    question?: GlobalQuizQuestion;
  }>(`/study-loop/sessions/${encodeURIComponent(sessionId)}/start-practice`, {
    method: "POST",
    body: JSON.stringify({ count }),
  });
  const quizSessionId =
    String(raw.practice_quiz_session_id || raw.quiz?.session_id || "").trim() ||
    String(raw.session_id || "").trim();
  return {
    session_id: quizSessionId,
    loop_session_id: raw.session_id,
    domain: String(raw.domain || raw.quiz?.domain || ""),
    question: (raw.quiz?.question ?? raw.question) as GlobalQuizQuestion | undefined,
  };
}

export async function fetchStudyLoopQuestions(opts?: { tag?: string; kind?: string }) {
  const qs = new URLSearchParams();
  if (opts?.tag) qs.set("tag", opts.tag);
  if (opts?.kind) qs.set("kind", opts.kind);
  const q = qs.toString();
  return quizRequest<{ items: Array<Record<string, unknown>>; count: number }>(
    `/study-loop/questions${q ? `?${q}` : ""}`
  );
}

export async function patchStudyLoopQuestion(questionId: string, body: Record<string, unknown>) {
  return quizRequest<Record<string, unknown>>(
    `/study-loop/questions/${encodeURIComponent(questionId)}`,
    { method: "PATCH", body: JSON.stringify(body) }
  );
}

export type QuizCodeRunOutcome = {
  name: string;
  passed: boolean;
  expected?: unknown;
  actual?: unknown;
  error?: string | null;
  hidden?: boolean;
  description?: string;
};

export type QuizCodeRunResult = {
  correct: boolean;
  feedback: string;
  all_passed: boolean;
  passed: number;
  total: number;
  compile_error?: string | null;
  timed_out?: boolean;
  outcomes?: QuizCodeRunOutcome[];
};

export async function runQuizCode(payload: {
  code: string;
  item?: Record<string, unknown>;
  item_id?: string;
}): Promise<QuizCodeRunResult> {
  return quizRequest<QuizCodeRunResult>("/code/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
