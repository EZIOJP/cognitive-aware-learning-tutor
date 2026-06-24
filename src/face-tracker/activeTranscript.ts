const KEY = "study:active-transcript";

export function getActiveTranscript(): string | null {
  try {
    const v = localStorage.getItem(KEY);
    return v?.trim() || null;
  } catch {
    return null;
  }
}

export function setActiveTranscript(filename: string): void {
  try {
    localStorage.setItem(KEY, filename);
  } catch {
    /* ignore */
  }
}
