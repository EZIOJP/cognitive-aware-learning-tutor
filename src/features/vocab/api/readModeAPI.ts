/**
 * Drop-in client API — same shapes as refernces/vocab readModeAPI.js (no Django).
 */
import {
  queryWordsByCriteria,
  markWordRead,
} from "../store/vocabStore";
import type { WordCriteria, PaginatedWords } from "../types";

type FetchOptions = { limit?: number; offset?: number };

async function byMasteryRange(
  min: number | undefined,
  max: number | undefined,
  options: FetchOptions = {}
): Promise<PaginatedWords> {
  return queryWordsByCriteria({
    limit: options.limit ?? 30,
    offset: options.offset ?? 0,
    ...(min != null ? { mastery_min: min } : {}),
    ...(max != null ? { mastery_max: max } : {}),
  });
}

export const fetchAllWords = (options: FetchOptions = {}) =>
  queryWordsByCriteria({
    limit: options.limit ?? 30,
    offset: options.offset ?? 0,
  });

export const fetchWordsWithProgress = fetchAllWords;

export const fetchLowMasteryWords = (options: FetchOptions = {}) =>
  byMasteryRange(undefined, 0, options);

export const fetchStrugglingWords = (options: FetchOptions = {}) =>
  byMasteryRange(undefined, -1, options);

export const fetchLearningWords = (options: FetchOptions = {}) =>
  byMasteryRange(0, 2, options);

export const fetchPracticingWords = (options: FetchOptions = {}) =>
  byMasteryRange(3, 5, options);

export const fetchMasteredWords = (options: FetchOptions = {}) =>
  byMasteryRange(6, undefined, options);

export const fetchDueReviewWords = (options: FetchOptions = {}) =>
  queryWordsByCriteria({
    due_for_review: true,
    limit: options.limit ?? 30,
    offset: options.offset ?? 0,
  });

export const fetchGroupWords = (
  groupNumber: number,
  options: FetchOptions = {}
) =>
  queryWordsByCriteria({
    group: groupNumber,
    limit: options.limit ?? 30,
    offset: options.offset ?? 0,
  });

export const fetchWordsByIds = (
  wordIds: number[] | string,
  options: FetchOptions = {}
) => {
  const ids = Array.isArray(wordIds) ? wordIds.join(",") : wordIds;
  return queryWordsByCriteria({
    word_ids: ids,
    limit: options.limit ?? 30,
    offset: options.offset ?? 0,
  });
};

export const fetchWordsByCriteria = (criteria: WordCriteria = {}) =>
  queryWordsByCriteria(criteria);

export const markSwipeRead = (wordId: number) => markWordRead(wordId);
export const markWordReadLegacy = markSwipeRead;
export const markMultipleWordsRead = (wordIds: number[]) =>
  Promise.allSettled(wordIds.map((id) => markWordRead(id)));

export const fetchDashboardData = async () => {
  const all = await queryWordsByCriteria({ limit: 9999, offset: 0 });
  const words = all.words;
  return {
    total_words: all.pagination.total_available,
    mastered: words.filter((w) => w.mastery >= 6).length,
    struggling: words.filter((w) => w.mastery < 0).length,
    due_reviews: words.filter((w) => w.is_due).length,
    average_mastery:
      words.length > 0
        ? words.reduce((s, w) => s + w.mastery, 0) / words.length
        : 0,
  };
};

export const ReadModeConfigs = {
  allWords: {
    title: "All Words",
    fetchWords: fetchWordsWithProgress,
    allowFiltering: true,
    markAsRead: true,
  },
  lowMastery: {
    title: "Low Mastery Words",
    fetchWords: fetchLowMasteryWords,
    allowFiltering: false,
    markAsRead: true,
  },
  struggling: {
    title: "Struggling Words",
    fetchWords: fetchStrugglingWords,
    allowFiltering: false,
    markAsRead: true,
  },
  learning: {
    title: "Learning Phase",
    fetchWords: fetchLearningWords,
    allowFiltering: true,
    markAsRead: true,
  },
  practicing: {
    title: "Practicing Phase",
    fetchWords: fetchPracticingWords,
    allowFiltering: true,
    markAsRead: false,
  },
  mastered: {
    title: "Mastered Words",
    fetchWords: fetchMasteredWords,
    allowFiltering: false,
    markAsRead: false,
  },
  dueReview: {
    title: "Due for Review",
    fetchWords: fetchDueReviewWords,
    allowFiltering: false,
    markAsRead: false,
  },
  cycle: {
    title: "Cycle Mode",
    fetchWords: fetchWordsWithProgress,
    allowFiltering: true,
    markAsRead: true,
  },
};
