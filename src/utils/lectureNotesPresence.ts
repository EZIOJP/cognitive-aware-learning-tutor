/** Module signal: Lecture Notes document open + reading (for SPA study credit). */

export type LectureNotesPresenceState = {
  notesLoaded: boolean;
  reading: boolean;
  documentId: string | null;
  title: string | null;
};

const EMPTY: LectureNotesPresenceState = {
  notesLoaded: false,
  reading: false,
  documentId: null,
  title: null,
};

let state: LectureNotesPresenceState = { ...EMPTY };
const listeners = new Set<() => void>();

export function getLectureNotesPresence(): LectureNotesPresenceState {
  return state;
}

export function setLectureNotesPresence(next: Partial<LectureNotesPresenceState> | null): void {
  if (next == null) {
    state = { ...EMPTY };
  } else {
    state = {
      notesLoaded: Boolean(next.notesLoaded),
      reading: Boolean(next.reading),
      documentId: next.documentId ?? null,
      title: next.title ?? null,
    };
  }
  listeners.forEach((fn) => fn());
}

export function subscribeLectureNotesPresence(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
