import {
  ensureWordsLoaded,
  mergeWord,
  loadWordsForRead,
  updateQuizAnswer,
} from "../store/vocabStore";
import type { WordWithProgress } from "../types";
import type {
  GroupSummary,
  QuizAttempt,
  QuizQuestion,
  QuizResults,
} from "./types";

const MASTERY_MASTERED = 6;
const GROUP_PROGRESS_KEY = "vocab:group-progress";

function loadGroupProgress(): Record<number, { completed_at?: string }> {
  try {
    return JSON.parse(localStorage.getItem(GROUP_PROGRESS_KEY) || "{}");
  } catch {
    return {};
  }
}

export function markGroupStudied(groupNumber: number) {
  const map = loadGroupProgress();
  map[groupNumber] = { completed_at: new Date().toISOString() };
  localStorage.setItem(GROUP_PROGRESS_KEY, JSON.stringify(map));
}

export async function getGroupsDetailed(): Promise<GroupSummary[]> {
  const words = await ensureWordsLoaded();
  const progressMap = JSON.parse(
    localStorage.getItem("vocab:user-progress") || "{}"
  );
  const groupProgress = loadGroupProgress();

  const byGroup = new Map<number, WordWithProgress[]>();

  for (const w of words) {
    const merged = mergeWord(w, progressMap[w.id]);
    const list = byGroup.get(merged.group_number) || [];
    list.push(merged);
    byGroup.set(merged.group_number, list);
  }

  return Array.from(byGroup.entries())
    .sort(([a], [b]) => a - b)
    .map(([group_number, groupWords]) => {
      const mastered = groupWords.filter((w) => w.mastery >= MASTERY_MASTERED).length;
      const notStarted = groupWords.filter((w) => w.mastery === 0).length;
      const needPractice = groupWords.filter(
        (w) => w.mastery > 0 && w.mastery < MASTERY_MASTERED
      ).length;
      const dueReview = groupWords.filter((w) => w.is_due).length;
      const words_started = groupWords.length - notStarted;
      const completion_percentage =
        groupWords.length > 0
          ? Math.round((mastered / groupWords.length) * 100)
          : 0;

      return {
        group_number,
        total_words: groupWords.length,
        words_started,
        words_mastered: mastered,
        completion_percentage,
        is_completed:
          groupProgress[group_number]?.completed_at != null ||
          completion_percentage >= 80,
        mastery_threshold: MASTERY_MASTERED,
        stats: {
          mastered,
          needPractice,
          dueReview,
          notStarted,
        },
      };
    });
}

export async function getDashboardStats() {
  const groups = await getGroupsDetailed();
  const all = await loadWordsForRead("all");
  const studied = all.filter((w) => w.times_asked > 0);
  const totalAsked = all.reduce((sum, w) => sum + w.times_asked, 0);
  const totalCorrect = all.reduce((sum, w) => sum + w.times_correct, 0);
  const progressMap = JSON.parse(localStorage.getItem("vocab:user-progress") || "{}");
  const suspendedWords = Object.values(progressMap).filter(
    (p: any) => p?.is_suspended === true
  ).length;
  const lastActivity = Object.values(progressMap).reduce<string | null>(
    (latest, p: any) => {
      const ts = typeof p?.last_practiced === "string" ? p.last_practiced : null;
      if (!ts) return latest;
      if (!latest) return ts;
      return new Date(ts) > new Date(latest) ? ts : latest;
    },
    null
  );

  return {
    total_groups: groups.length,
    total_words: all.length,
    studied_words: studied.length,
    mastered: all.filter((w) => w.mastery >= MASTERY_MASTERED).length,
    due_reviews: all.filter((w) => w.is_due).length,
    low_mastery: all.filter((w) => w.mastery <= 0).length,
    struggling: all.filter((w) => w.mastery < 0).length,
    suspended_words: suspendedWords,
    overall_accuracy:
      totalAsked > 0 ? Math.round((totalCorrect / totalAsked) * 100) : 0,
    study_coverage_pct:
      all.length > 0 ? Math.round((studied.length / all.length) * 100) : 0,
    last_activity: lastActivity,
  };
}

export async function loadGroupWords(
  groupNumber: number
): Promise<WordWithProgress[]> {
  return loadWordsForRead("all", groupNumber);
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function buildQuizQuestions(words: WordWithProgress[]): QuizQuestion[] {
  const allMeanings = words.map((w) => w.meaning).filter(Boolean);

  return shuffle(words).map((w) => {
    const distractors = shuffle(
      allMeanings.filter((m) => m !== w.meaning)
    ).slice(0, 3);
    const options = shuffle([w.meaning, ...distractors]);
    return {
      word_id: w.id,
      word: w.word,
      pronunciation: w.pronunciation,
      options,
      correct_answer: w.meaning,
    };
  });
}

export async function submitQuizAnswer(
  word: WordWithProgress,
  selectedAnswer: string,
  timeTaken: number
): Promise<QuizAttempt> {
  const isCorrect = selectedAnswer.trim() === word.meaning.trim();
  const mastery_before = word.mastery;
  const updated = await updateQuizAnswer(word.id, isCorrect);

  return {
    word_id: word.id,
    word: word.word,
    user_answer: selectedAnswer,
    correct_answer: word.meaning,
    is_correct: isCorrect,
    mastery_before,
    mastery_after: updated.mastery,
    time_taken: timeTaken,
  };
}

export function buildQuizResults(
  sessionId: string,
  attempts: QuizAttempt[]
): QuizResults {
  const correct = attempts.filter((a) => a.is_correct).length;
  const improved = attempts.filter(
    (a) => a.mastery_after > a.mastery_before
  ).length;

  return {
    session_id: sessionId,
    attempts,
    performance: {
      total_questions: attempts.length,
      correct_answers: correct,
      accuracy_rate:
        attempts.length > 0
          ? Math.round((correct / attempts.length) * 100)
          : 0,
      words_improved: improved,
    },
  };
}

export function getLowMasteryFromAttempts(
  attempts: QuizAttempt[],
  words: WordWithProgress[]
): WordWithProgress[] {
  const lowIds = new Set(
    attempts
      .filter((a) => (a.mastery_after ?? 0) <= 0)
      .map((a) => a.word_id)
  );
  return words.filter((w) => lowIds.has(w.id));
}
