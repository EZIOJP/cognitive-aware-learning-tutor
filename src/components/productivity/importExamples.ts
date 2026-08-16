/** Copy-paste JSON examples for Schedule → Import. Daily examples use today when loaded. */

export type ImportExampleKind = "daily" | "weekly" | "shift" | "exam" | "weekend" | "semester";

function todayIso(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function getDailyImportExample(): string {
  return JSON.stringify(
    {
      type: "daily",
      name: "Today",
      date: todayIso(),
      apply_to_planner: true,
      daily_slots: [
        { start: "06:30", end: "07:00", title: "Bible / devotion", category: "spiritual", color: "#a78bfa" },
        { start: "07:00", end: "07:30", title: "Bath / self-care", category: "personal", color: "#06b6d4" },
        { start: "08:00", end: "08:30", title: "Breakfast", category: "food" },
        { start: "09:00", end: "11:00", title: "Deep work — study", category: "study" },
        { start: "11:00", end: "11:15", title: "Break", category: "break" },
        { start: "14:00", end: "15:30", title: "Reading / lecture", category: "reading" },
        { start: "19:30", end: "20:15", title: "Dinner", category: "food" },
        { start: "20:15", end: "20:45", title: "Get ready to sleep", category: "personal", color: "#6366f1" },
      ],
    },
    null,
    2,
  );
}

export const WEEKLY_IMPORT_EXAMPLE = JSON.stringify(
  {
    type: "weekly",
    name: "Spring semester week",
    tasks: [
      { title: "Linear Algebra", description: "Lecture + problems" },
      { title: "Python / NumPy", description: "Practice + notes" },
      { title: "GRE vocab", description: "Anki + review" },
    ],
    slots: [
      { day: "mon", start: "09:00", end: "11:00", task_index: 0, title: "Linear Algebra", category: "lecture" },
      { day: "mon", start: "14:00", end: "16:00", task_index: 1, title: "Python study", category: "study" },
      { day: "wed", start: "09:00", end: "11:00", task_index: 0, title: "Linear Algebra lab", category: "lecture" },
      { day: "fri", start: "07:00", end: "07:45", task_index: 2, title: "GRE vocab", category: "review" },
      { day: "sat", start: "10:00", end: "12:00", task_index: 1, title: "Project work", category: "study" },
    ],
  },
  null,
  2,
);

export const SHIFT_IMPORT_EXAMPLE = JSON.stringify(
  {
    type: "weekly",
    name: "2-2-3 rotating shift",
    tasks: [
      { title: "Day shift", description: "06:00–14:00 on-site" },
      { title: "Swing shift", description: "14:00–22:00 on-site" },
      { title: "Off / recovery", description: "Sleep + errands" },
    ],
    slots: [
      { day: "mon", start: "06:00", end: "14:00", task_index: 0, title: "Day shift", category: "work" },
      { day: "tue", start: "06:00", end: "14:00", task_index: 0, title: "Day shift", category: "work" },
      { day: "wed", start: "14:00", end: "22:00", task_index: 1, title: "Swing shift", category: "work" },
      { day: "thu", start: "14:00", end: "22:00", task_index: 1, title: "Swing shift", category: "work" },
      { day: "fri", start: "08:00", end: "22:00", task_index: 2, title: "Off day", category: "personal" },
      { day: "sat", start: "10:00", end: "12:00", task_index: 2, title: "Grocery / chores", category: "personal" },
      { day: "sun", start: "18:00", end: "21:00", task_index: 2, title: "Meal prep", category: "food" },
    ],
  },
  null,
  2,
);

export function getExamImportExample(): string {
  return JSON.stringify(
    {
      type: "daily",
      name: "Exam crunch day",
      date: todayIso(),
      apply_to_planner: true,
      daily_slots: [
        { start: "06:00", end: "06:30", title: "Wake + stretch", category: "personal" },
        { start: "06:30", end: "08:30", title: "Past papers — timed", category: "study", color: "#ef4444" },
        { start: "08:30", end: "09:00", title: "Break", category: "break" },
        { start: "09:00", end: "11:00", title: "Weak topics drill", category: "study", color: "#f97316" },
        { start: "11:00", end: "11:30", title: "Lunch", category: "food" },
        { start: "11:30", end: "13:30", title: "Flashcards + formulas", category: "review" },
        { start: "14:00", end: "16:00", title: "Mock exam block", category: "study", color: "#ef4444" },
        { start: "16:00", end: "16:30", title: "Walk / reset", category: "break" },
        { start: "17:00", end: "19:00", title: "Error review", category: "review" },
        { start: "21:00", end: "21:30", title: "Light recap only", category: "reading" },
      ],
    },
    null,
    2,
  );
}

export const WEEKEND_IMPORT_EXAMPLE = JSON.stringify(
  {
    type: "weekly",
    name: "Weekend focus block",
    tasks: [
      { title: "Side project", description: "Ship one feature" },
      { title: "Fitness", description: "Gym + walk" },
      { title: "Household", description: "Chores + meal prep" },
    ],
    slots: [
      { day: "sat", start: "08:00", end: "09:00", task_index: 2, title: "Slow morning", category: "personal" },
      { day: "sat", start: "09:30", end: "12:30", task_index: 0, title: "Side project deep work", category: "study" },
      { day: "sat", start: "14:00", end: "15:30", task_index: 1, title: "Gym", category: "fitness" },
      { day: "sun", start: "10:00", end: "11:30", task_index: 2, title: "Meal prep", category: "food" },
      { day: "sun", start: "14:00", end: "17:00", task_index: 0, title: "Project polish", category: "study" },
      { day: "sun", start: "18:00", end: "19:00", title: "Week review + plan", category: "review" },
    ],
  },
  null,
  2,
);

export const SEMESTER_IMPORT_EXAMPLE = JSON.stringify(
  {
    type: "weekly",
    name: "Full semester grid",
    tasks: [
      { title: "Calculus II", description: "MWF lecture" },
      { title: "Data Structures", description: "Tue lab + Thu seminar" },
      { title: "GRE prep", description: "Daily vocab + weekend mocks" },
      { title: "Research reading", description: "Papers + notes" },
    ],
    slots: [
      { day: "mon", start: "08:00", end: "09:30", task_index: 0, title: "Calculus lecture", category: "lecture" },
      { day: "mon", start: "14:00", end: "16:00", task_index: 3, title: "Research reading", category: "reading" },
      { day: "tue", start: "10:00", end: "12:00", task_index: 1, title: "DS lab", category: "lecture" },
      { day: "wed", start: "08:00", end: "09:30", task_index: 0, title: "Calculus lecture", category: "lecture" },
      { day: "wed", start: "16:00", end: "17:00", task_index: 2, title: "GRE vocab", category: "review" },
      { day: "thu", start: "13:00", end: "14:30", task_index: 1, title: "DS seminar", category: "lecture" },
      { day: "fri", start: "08:00", end: "09:30", task_index: 0, title: "Calculus lecture", category: "lecture" },
      { day: "fri", start: "07:00", end: "07:45", task_index: 2, title: "GRE morning drill", category: "review" },
      { day: "sat", start: "09:00", end: "12:00", task_index: 2, title: "GRE mock section", category: "study" },
      { day: "sun", start: "19:00", end: "20:00", task_index: 2, title: "Week planning", category: "review" },
    ],
  },
  null,
  2,
);

const EXAMPLE_BUILDERS: Record<ImportExampleKind, () => string> = {
  daily: getDailyImportExample,
  weekly: () => WEEKLY_IMPORT_EXAMPLE,
  shift: () => SHIFT_IMPORT_EXAMPLE,
  exam: getExamImportExample,
  weekend: () => WEEKEND_IMPORT_EXAMPLE,
  semester: () => SEMESTER_IMPORT_EXAMPLE,
};

export function getImportExample(kind: ImportExampleKind): string {
  return EXAMPLE_BUILDERS[kind]();
}

export const IMPORT_EXAMPLE_KINDS: ImportExampleKind[] = [
  "daily",
  "weekly",
  "shift",
  "exam",
  "weekend",
  "semester",
];

export const IMPORT_EXAMPLE_LABELS: Record<ImportExampleKind, string> = {
  daily: "Daily",
  weekly: "Weekly",
  shift: "Shift work",
  exam: "Exam day",
  weekend: "Weekend",
  semester: "Semester",
};

export const IMPORT_EXAMPLE_HINTS: Record<ImportExampleKind, string> = {
  daily: "Fills today's planner immediately. Edit times/titles, then Import.",
  weekly: "Saves a weekly template — then click Week → planner.",
  shift: "Rotating shift pattern (day / swing / off). Save template, generate week.",
  exam: "High-intensity single day — applies directly to today's calendar.",
  weekend: "Sat–Sun blocks for projects, fitness, and planning.",
  semester: "Full M–Sun lecture + study grid for a typical term.",
};
