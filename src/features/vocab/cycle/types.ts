import type { WordWithProgress } from "../types";

export type CyclePhase =
  | "dashboard"
  | "reading"
  | "quiz"
  | "report"
  | "low_mastery_prompt"
  | "low_mastery_reading"
  | "low_mastery_quiz"
  | "low_mastery_report";

export interface GroupSummary {
  group_number: number;
  total_words: number;
  words_started: number;
  words_mastered: number;
  completion_percentage: number;
  is_completed: boolean;
  mastery_threshold: number;
  stats: {
    mastered: number;
    needPractice: number;
    dueReview: number;
    notStarted: number;
  };
}

export interface CycleGroupStart {
  groupNumber: number;
  totalWords: number;
  wordsStarted: number;
  wordsMastered: number;
  isCompleted: boolean;
  words: WordWithProgress[];
}

export interface QuizAttempt {
  word_id: number;
  word: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  mastery_before: number;
  mastery_after: number;
  time_taken: number;
}

export interface QuizResults {
  session_id: string;
  attempts: QuizAttempt[];
  performance: {
    total_questions: number;
    correct_answers: number;
    accuracy_rate: number;
    words_improved: number;
  };
}

export interface QuizQuestion {
  word_id: number;
  word: string;
  pronunciation?: string;
  options: string[];
  correct_answer: string;
}
