export type GapSeverity = "high" | "medium" | "low";

export type GapItem = {
  topic: string;
  lecture_excerpt: string;
  reference_excerpt: string;
  severity: GapSeverity;
  suggestion: string;
};

export type GapAnalysisResult = {
  summary: string;
  gaps: GapItem[];
  aligned_topics: string[];
  source?: string;
  summary_markdown?: string;
};

export type QuizQuestion = {
  id: string;
  question: string;
  options: string[];
  answer_index: number;
  explanation?: string;
  hint?: string;
  concept?: string;
  topic_id?: string;
  topic?: string;
  note_path?: string;
  tags?: string[];
  source_chunk_id?: string;
  citation?: string;
};

export type QuizFocus = "mixed" | "concept" | "coding" | "cover_all";

export type NoteTopicOption = {
  topic_id: string;
  title: string;
  label: string;
  char_count?: number;
  source?: string;
};

export type CodeDrill = {
  id: string;
  title: string;
  language: string;
  prompt: string;
  starter_code: string;
  hint?: string;
  source_chunk_id?: string;
  citation?: string;
};

export type StudySessionItem = {
  id: string;
  kind: "quiz" | "exercise" | "note";
  title: string;
  content: string;
  detail: string;
  approved: boolean;
};

export type SyncSavedItem = {
  id: string;
  relative_path: string;
  title: string;
  kind: string;
};
