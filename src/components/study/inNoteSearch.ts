export type InNoteMatch = {
  line: number;
  snippet: string;
  charOffset: number;
};

/** Lightweight in-memory search — one pass over lines, capped results. */
export function findInNoteContent(content: string, query: string, max = 60): InNoteMatch[] {
  const q = query.trim().toLowerCase();
  if (!q || !content) return [];

  const lines = content.split("\n");
  const out: InNoteMatch[] = [];
  let offset = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i] ?? "";
    const lower = line.toLowerCase();
    let idx = 0;
    while ((idx = lower.indexOf(q, idx)) !== -1) {
      const start = Math.max(0, idx - 36);
      const end = Math.min(line.length, idx + q.length + 48);
      let snippet = line.slice(start, end).trim();
      if (start > 0) snippet = `…${snippet}`;
      if (end < line.length) snippet = `${snippet}…`;
      out.push({ line: i + 1, snippet, charOffset: offset + idx });
      if (out.length >= max) return out;
      idx += q.length || 1;
    }
    offset += line.length + 1;
  }

  return out;
}

export function scrollToCharOffset(
  container: HTMLElement | null | undefined,
  content: string,
  charOffset: number,
) {
  if (!container || !content) return;
  const ratio = charOffset / Math.max(1, content.length);
  const maxScroll = container.scrollHeight - container.clientHeight;
  container.scrollTop = Math.max(0, ratio * maxScroll);
}
