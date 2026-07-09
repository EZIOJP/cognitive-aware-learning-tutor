import { config } from "../config";

const BASE = config.backend.apiUrl;
const TOKEN_KEY = "vocab:auth-token";

function headers(json = true): HeadersInit {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

function apiErrorMessage(data: unknown, status: number): string {
  if (data && typeof data === "object") {
    const envelope = data as { error?: { message?: string }; detail?: unknown };
    if (envelope.error?.message) return envelope.error.message;
    const detail = envelope.detail;
    if (typeof detail === "string") return detail;
  }
  return `HTTP ${status}`;
}

export type BookSlot = {
  subject_id: string;
  label: string;
  short_label: string;
  description: string;
  expected_filename: string;
  document_id: string;
  format: string;
  file_present: boolean;
  file_size_bytes: number;
  metadata_present: boolean;
  ingested_chunks: number;
  auto_chapters: number[] | null;
  ready: boolean;
};

export type CorpusOverview = {
  books: BookSlot[];
  corpus: {
    available: boolean;
    total_chunks: number;
    documents: {
      document_id: string;
      title: string;
      source_type: string;
      chunks: number;
      source_path: string;
    }[];
  };
  transcripts: {
    filename: string;
    size_bytes: number;
    ingested_chunks: number;
  }[];
  paths: {
    raw_library: string;
    transcripts: string;
    setup_log: string;
  };
  environment?: {
    pandoc_available: boolean;
  };
};

export type CorpusJob = {
  job_id: string;
  kind: string;
  status: "queued" | "running" | "done" | "error";
  progress: number;
  message: string;
  logs: string[];
  result: Record<string, unknown> | null;
  error: string | null;
  started_at: string;
  finished_at: string;
};

export async function fetchCorpusOverview(): Promise<CorpusOverview> {
  const res = await fetch(`${BASE}/api/corpus/overview`, { headers: headers(false) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as CorpusOverview;
}

export async function fetchCorpusJob(jobId?: string): Promise<CorpusJob | null> {
  const q = jobId ? `?job_id=${encodeURIComponent(jobId)}` : "";
  const res = await fetch(`${BASE}/api/corpus/job${q}`, { headers: headers(false) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return (data as { job: CorpusJob | null }).job;
}

export async function runCorpusSetup(opts?: {
  mml_chapters?: number[];
  transcript_limit?: number;
  ingest_full_books?: boolean;
  skip_indexed_books?: boolean;
}): Promise<CorpusJob> {
  const res = await fetch(`${BASE}/api/corpus/run-setup`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      mml_chapters: opts?.mml_chapters ?? [1, 2],
      transcript_limit: opts?.transcript_limit ?? 3,
      ingest_full_books: opts?.ingest_full_books ?? true,
      skip_indexed_books: opts?.skip_indexed_books ?? true,
      test_query: true,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return (data as { job: CorpusJob }).job;
}

export async function ingestCorpusBook(
  subjectId: string,
  chapters?: number[],
): Promise<CorpusJob> {
  const res = await fetch(`${BASE}/api/corpus/ingest-book`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ subject_id: subjectId, chapters: chapters ?? null }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return (data as { job: CorpusJob }).job;
}

export async function ingestAllCorpusBooks(opts?: {
  skip_indexed?: boolean;
  force?: boolean;
}): Promise<CorpusJob> {
  const res = await fetch(`${BASE}/api/corpus/ingest-all-books`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      skip_indexed: opts?.skip_indexed ?? true,
      force: opts?.force ?? false,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return (data as { job: CorpusJob }).job;
}

export async function uploadCorpusBook(subjectId: string, file: File): Promise<unknown> {
  const form = new FormData();
  form.append("file", file);
  const token = localStorage.getItem(TOKEN_KEY);
  const h: Record<string, string> = {};
  if (token) h.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}/api/corpus/upload/${encodeURIComponent(subjectId)}`, {
    method: "POST",
    headers: h,
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data;
}

export async function fetchCorpusLog(lines = 80): Promise<string> {
  const res = await fetch(`${BASE}/api/corpus/log?lines=${lines}`, { headers: headers(false) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return (data as { log: string }).log;
}

export type GroundedNotesResult = {
  mode: string;
  filename?: string;
  notes_path?: string;
  markdown?: string;
  chunk_count?: number;
  corpus_handoff?: {
    transcript_chunks?: number;
    note_chunks?: number;
  };
};

export async function generateGroundedNotes(opts: {
  transcriptFile: string;
  topic?: string;
  title?: string;
  folderPath?: string;
}): Promise<GroundedNotesResult> {
  const res = await fetch(`${BASE}/api/corpus/generate-notes-grounded`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      transcript_file: opts.transcriptFile,
      topic: opts.topic ?? "",
      title: opts.title ?? "",
      folder_path: opts.folderPath ?? "",
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as GroundedNotesResult;
}

export async function ingestLectureToCorpus(opts: {
  transcriptFile: string;
  notePath?: string;
}): Promise<unknown> {
  const res = await fetch(`${BASE}/api/corpus/ingest-lecture`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      transcript_file: opts.transcriptFile,
      note_path: opts.notePath ?? "",
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
