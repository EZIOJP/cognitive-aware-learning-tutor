export interface WordBreakdown {
  prefix?: string;
  root?: string;
  suffix?: string;
}

export interface WordExample {
  text: string;
  tags?: string[];
  style?: string;
}

export interface VocabWord {
  id: number;
  word: string;
  pronunciation?: string;
  meaning: string;
  connotation?: string;
  group_number: number;
  story_mnemonic?: string;
  etymology?: string;
  word_breakdown?: WordBreakdown;
  category?: string;
  difficulty_level?: string;
  synonyms?: string[];
  antonyms?: string[];
  word_grouping?: string[];
  examples?: WordExample[];
  tags?: string[];
  external_links?: Record<string, string>;
}

export interface WordProgress {
  mastery: number;
  times_asked: number;
  times_correct: number;
  consecutive_correct: number;
  due_date: string | null;
  last_practiced: string;
  is_learning: boolean;
}

export interface WordWithProgress extends VocabWord {
  mastery: number;
  times_asked: number;
  times_correct: number;
  accuracy_rate: number;
  is_due: boolean;
  consecutive_correct?: number;
}

export interface PaginatedWords {
  words: WordWithProgress[];
  pagination: {
    limit: number;
    offset: number;
    returned: number;
    total_available: number;
    has_more: boolean;
  };
}

export interface WordCriteria {
  limit?: number;
  offset?: number;
  mastery_min?: number | string;
  mastery_max?: number | string;
  group?: number | string;
  due_for_review?: boolean | string;
  word_ids?: string;
}
