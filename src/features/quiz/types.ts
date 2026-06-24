export type QuizDomain = "vocab" | "math" | "study" | "code" | "mixed" | "review" | "deck";

export type QuizFormat = "mcq" | "free_text" | "code";

export type GlobalQuizQuestion = {
  domain: QuizDomain;
  format: QuizFormat;
  index: number;
  total: number;
  item_id: string;
  prompt: string;
  options?: string[];
  starter_code?: string;
  meta?: {
    hint?: string;
    topic?: string;
    note_path?: string;
    time_limit_sec?: number;
    per_question_sec?: number;
    session_deadline_ms?: number;
    answer_index?: number;
    review_card_id?: number;
    [key: string]: unknown;
  };
};

export type GlobalQuizAnswerResult = {
  correct: boolean;
  feedback: string;
  mastery?: number;
  complete: boolean;
  next_question?: GlobalQuizQuestion | null;
  added_to_review?: boolean;
};

export type QuizSessionSummary = {
  correct: number;
  total: number;
  accuracy_pct?: number;
  total_time_ms?: number;
  attempts?: Array<{
    item_id?: string;
    domain?: string;
    correct?: boolean;
    label?: string;
    time_taken_ms?: number;
  }>;
  domain?: string;
};

export type DueReviewItem = {
  card_id?: number | null;
  domain: string;
  item_id: string;
  label: string;
  topic?: string | null;
  mastery: number;
  stability?: number;
  difficulty?: number;
  due_date?: string | null;
  format?: string;
  note_path?: string;
  hint?: string;
  payload?: Record<string, unknown>;
};

export type QuizBacklog = {
  total_cards: number;
  due_count: number;
  by_domain: Record<string, number>;
  deck_count: number;
  next_due?: string | null;
  recommended_action: "sign_in" | "review_due" | "start_vocab" | "lecture_notes";
};

export type QuizDeckSummary = {
  id: number;
  title: string;
  topic?: string | null;
  domain: string;
  item_count: number;
  time_limit_sec?: number | null;
  updated_at?: string | null;
};

export type QuizQuestion = {
  id: string;
  question: string;
  options: string[];
  answer_index: number;
  explanation?: string;
  hint?: string;
};

export type CodeDrill = {
  id: string;
  title: string;
  language: string;
  prompt: string;
  starter_code: string;
  hint?: string;
};
