import { config } from "../config";
import type {
  CodeDrill,
  GapAnalysisResult,
  QuizQuestion,
  StudySessionItem,
  SyncSavedItem,
} from "../components/study/studySessionTypes";

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

export type LlmConfig = {
  enabled: boolean;
  provider: string;
  base_url: string;
  model: string;
  max_tokens: number;
  reachable: boolean;
  corpus_grounded_notes?: boolean;
  corpus_available?: boolean;
};

export type LlmOverrides = {
  llm_provider?: string;
  llm_base_url?: string;
  llm_model?: string;
};

const LLM_PREFS_KEY = "lecture-notes:llm";
const LLM_PREFS_MIGRATION_KEY = "lecture-notes:llm-migration-v2";

export function loadLlmPrefs(): LlmOverrides {
  try {
    const raw = localStorage.getItem(LLM_PREFS_KEY);
    const prefs: LlmOverrides = raw ? (JSON.parse(raw) as LlmOverrides) : {};
    if (!localStorage.getItem(LLM_PREFS_MIGRATION_KEY) && prefs.llm_provider === "gemini") {
      const migrated: LlmOverrides = {
        llm_provider: "lmstudio",
        llm_base_url: prefs.llm_base_url ?? "http://127.0.0.1:1234",
        llm_model: "google/gemma-4-e4b",
      };
      localStorage.setItem(LLM_PREFS_KEY, JSON.stringify(migrated));
      localStorage.setItem(LLM_PREFS_MIGRATION_KEY, "1");
      return migrated;
    }
    return prefs;
  } catch {
    return {};
  }
}

export function saveLlmPrefs(prefs: LlmOverrides): void {
  localStorage.setItem(LLM_PREFS_KEY, JSON.stringify(prefs));
}

export async function getLlmConfig(overrides?: LlmOverrides): Promise<LlmConfig> {
  const params = new URLSearchParams();
  if (overrides?.llm_provider) params.set("llm_provider", overrides.llm_provider);
  if (overrides?.llm_base_url) params.set("llm_base_url", overrides.llm_base_url);
  if (overrides?.llm_model) params.set("llm_model", overrides.llm_model);
  const qs = params.toString();
  const res = await fetch(`${BASE}/api/transcripts/llm-config${qs ? `?${qs}` : ""}`, {
    headers: headers(),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as LlmConfig;
}

export type TranscriptFile = {
  filename: string;
  size_bytes: number;
  modified: number;
};

export type NoteFile = TranscriptFile & {
  title?: string;
  topic?: string | null;
  source?: string;
  section_count?: number;
  relative_path?: string;
  folder_path?: string;
  kind?: string;
};

export type LibraryTree = {
  root: {
    path: string;
    name: string;
    folders: LibraryFolderNode[];
    files: LibraryFile[];
  };
};

export type LibraryFolderNode = {
  path: string;
  name: string;
  folders: LibraryFolderNode[];
  files: LibraryFile[];
};

export type LibraryFile = {
  relative_path: string;
  title: string;
  kind: string;
  topic?: string | null;
  source?: string;
  created_at?: number;
  read_scroll_top?: number;
  bookmark_scroll_top?: number | null;
};

export async function listTranscripts(): Promise<TranscriptFile[]> {
  const res = await fetch(`${BASE}/api/transcripts`, { headers: headers() });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return (data as { items: TranscriptFile[] }).items ?? [];
}

export async function indexNote(filename: string): Promise<{ indexed_nodes: number; note_path: string }> {
  const res = await fetch(`${BASE}/api/transcripts/index-note`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ note_path: filename }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as { indexed_nodes: number; note_path: string };
}

export async function listNoteTopics(): Promise<string[]> {
  const res = await fetch(`${BASE}/api/transcripts/notes/topics`, { headers: headers() });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return (data as { topics: string[] }).topics ?? [];
}

export async function getNoteContent(relativePath: string): Promise<string> {
  const encoded = relativePath
    .split("/")
    .map((s) => encodeURIComponent(s))
    .join("/");
  const res = await fetch(`${BASE}/api/transcripts/library/files/${encoded}/content`, {
    headers: headers(),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return (data as { content: string }).content;
}

export async function saveNoteContent(relativePath: string, content: string): Promise<void> {
  const encoded = relativePath
    .split("/")
    .map((s) => encodeURIComponent(s))
    .join("/");
  const res = await fetch(`${BASE}/api/transcripts/library/files/${encoded}/content`, {
    method: "PUT",
    headers: headers(),
    body: JSON.stringify({ content }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
}

export async function regenerateNoteBlock(opts: {
  block_type: "mermaid" | "code";
  language: string;
  content: string;
  error?: string;
  instruction?: string;
  mode?: "fix" | "polish";
  note_context?: string;
  llm?: LlmOverrides;
}): Promise<{ content: string }> {
  const res = await fetch(`${BASE}/api/transcripts/library/regenerate-block`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      block_type: opts.block_type,
      language: opts.language,
      content: opts.content,
      error: opts.error,
      instruction: opts.instruction,
      mode: opts.mode ?? "fix",
      note_context: opts.note_context,
      llm_provider: opts.llm?.llm_provider,
      llm_base_url: opts.llm?.llm_base_url,
      llm_model: opts.llm?.llm_model,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as { content: string };
}

export async function regenerateNoteSelection(opts: {
  selection: string;
  note_context?: string;
  instruction?: string;
  llm?: LlmOverrides;
}): Promise<{ content: string }> {
  const res = await fetch(`${BASE}/api/transcripts/library/regenerate-selection`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      selection: opts.selection,
      note_context: opts.note_context,
      instruction: opts.instruction,
      llm_provider: opts.llm?.llm_provider,
      llm_base_url: opts.llm?.llm_base_url,
      llm_model: opts.llm?.llm_model,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as { content: string };
}

export type RepairBlockDetail = {
  index: number;
  lang: string;
  method: string;
  status: string;
};

export async function repairAllNoteBlocks(opts: {
  content: string;
  use_llm?: boolean;
  llm?: LlmOverrides;
}): Promise<{ content: string; fixed_count: number; details: RepairBlockDetail[] }> {
  const res = await fetch(`${BASE}/api/transcripts/library/repair-all-blocks`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      content: opts.content,
      use_llm: opts.use_llm ?? true,
      llm_provider: opts.llm?.llm_provider,
      llm_base_url: opts.llm?.llm_base_url,
      llm_model: opts.llm?.llm_model,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as { content: string; fixed_count: number; details: RepairBlockDetail[] };
}

export async function repairAndSaveNote(
  relativePath: string,
  opts: { use_llm?: boolean; llm?: LlmOverrides } = {},
): Promise<{ content: string; fixed_count: number; details: RepairBlockDetail[] }> {
  const encoded = relativePath
    .split("/")
    .map((s) => encodeURIComponent(s))
    .join("/");
  const res = await fetch(`${BASE}/api/transcripts/library/files/${encoded}/repair-all-blocks`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      use_llm: opts.use_llm ?? true,
      llm_provider: opts.llm?.llm_provider,
      llm_base_url: opts.llm?.llm_base_url,
      llm_model: opts.llm?.llm_model,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as { content: string; fixed_count: number; details: RepairBlockDetail[] };
}

export type NoteExportFormat = "pdf" | "docx";

async function downloadExportResponse(res: Response, fallbackName: string): Promise<void> {
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data, res.status));
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = /filename="([^"]+)"/.exec(disposition);
  const filename = match?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function exportNoteFile(relativePath: string, format: NoteExportFormat): Promise<void> {
  const encoded = encodeLibraryPath(relativePath);
  const res = await fetch(`${BASE}/api/transcripts/library/files/${encoded}/export?format=${format}`, {
    headers: headers(),
  });
  await downloadExportResponse(res, `note.${format}`);
}

export async function exportLibraryFolder(folderPath: string, format: NoteExportFormat): Promise<void> {
  const url =
    folderPath.trim() === ""
      ? `${BASE}/api/transcripts/library/folders/export?format=${format}`
      : `${BASE}/api/transcripts/library/folders/${encodeLibraryPath(folderPath)}/export?format=${format}`;
  const res = await fetch(url, { headers: headers() });
  await downloadExportResponse(res, `folder_notes.${format}`);
}

export async function fetchLibraryTree(): Promise<LibraryTree> {
  const res = await fetch(`${BASE}/api/transcripts/library/tree`, { headers: headers() });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as LibraryTree;
}

export async function createLibraryFolder(folderPath: string): Promise<{ folder_path: string }> {
  const res = await fetch(`${BASE}/api/transcripts/library/folders`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ folder_path: folderPath }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as { folder_path: string };
}

export async function createLibraryFile(
  title: string,
  folderPath: string,
  kind: string,
): Promise<NoteFile> {
  const res = await fetch(`${BASE}/api/transcripts/library/files`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ title, folder_path: folderPath, kind }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as NoteFile;
}

export async function updateLibraryFile(
  relativePath: string,
  patch: { kind?: string; title?: string; dest_folder?: string; new_title?: string },
): Promise<NoteFile> {
  const encoded = relativePath
    .split("/")
    .map((s) => encodeURIComponent(s))
    .join("/");
  const res = await fetch(`${BASE}/api/transcripts/library/files/${encoded}`, {
    method: "PATCH",
    headers: headers(),
    body: JSON.stringify(patch),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as NoteFile;
}

function encodeLibraryPath(relativePath: string): string {
  return relativePath
    .split("/")
    .map((s) => encodeURIComponent(s))
    .join("/");
}

export async function deleteLibraryFile(relativePath: string): Promise<void> {
  const res = await fetch(`${BASE}/api/transcripts/library/files/${encodeLibraryPath(relativePath)}`, {
    method: "DELETE",
    headers: headers(),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
}

export async function deleteLibraryFolder(folderPath: string): Promise<void> {
  const encoded = encodeLibraryPath(folderPath);
  const res = await fetch(`${BASE}/api/transcripts/library/folders/${encoded}`, {
    method: "DELETE",
    headers: headers(),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
}

export async function updateReadingState(
  relativePath: string,
  patch: {
    read_scroll_top?: number;
    bookmark_scroll_top?: number;
    set_bookmark_from_read?: boolean;
  },
): Promise<{ read_scroll_top: number; bookmark_scroll_top: number | null }> {
  const res = await fetch(
    `${BASE}/api/transcripts/library/files/${encodeLibraryPath(relativePath)}/reading`,
    {
      method: "PATCH",
      headers: headers(),
      body: JSON.stringify(patch),
    },
  );
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as { read_scroll_top: number; bookmark_scroll_top: number | null };
}

export async function summarizeLibraryFolder(
  folderPath: string,
  title?: string,
  llm?: LlmOverrides,
): Promise<{ relative_path: string; title: string; source_count: number }> {
  const res = await fetch(`${BASE}/api/transcripts/library/folders/summarize`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      folder_path: folderPath,
      title: title ?? "",
      llm_provider: llm?.llm_provider,
      llm_base_url: llm?.llm_base_url,
      llm_model: llm?.llm_model,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as { relative_path: string; title: string; source_count: number };
}

export type GenerateNotesOptions = {
  title?: string;
  topic?: string;
  aggressiveDedup?: boolean;
  folderPath?: string;
  referencePaths?: string[];
  contextFolder?: string;
  refineSecondPass?: boolean;
  enrichWithReferences?: boolean;
  useSemanticGrouping?: boolean;
  useTagExtraction?: boolean;
  fastMode?: boolean;
  llm?: LlmOverrides;
};

export async function generateNotes(
  transcriptFile: string,
  options: GenerateNotesOptions = {},
): Promise<{
  filename: string;
  path: string;
  corpus_handoff?: { transcript_chunks?: number; note_chunks?: number };
}> {
  const res = await fetch(`${BASE}/api/transcripts/notes/generate`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      transcript_file: transcriptFile,
      title: options.title ?? "",
      topic: options.topic ?? "",
      folder_path: options.folderPath ?? "",
      reference_paths: options.referencePaths ?? [],
      context_folder: options.contextFolder ?? "",
      aggressive_dedup: options.aggressiveDedup ?? false,
      use_semantic_grouping: options.useSemanticGrouping ?? true,
      refine_second_pass: options.refineSecondPass ?? false,
      enrich_with_references: options.enrichWithReferences ?? true,
      use_tag_extraction: options.useTagExtraction ?? false,
      fast_mode: options.fastMode ?? false,
      llm_provider: options.llm?.llm_provider,
      llm_base_url: options.llm?.llm_base_url,
      llm_model: options.llm?.llm_model,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as {
    filename: string;
    path: string;
    corpus_handoff?: { transcript_chunks?: number; note_chunks?: number };
  };
}

export async function generateNotesFromToday(
  options: Omit<GenerateNotesOptions, "referencePaths" | "contextFolder"> = {},
): Promise<{ filename: string; path: string }> {
  const res = await fetch(`${BASE}/api/transcripts/notes/generate-today`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      title: options.title ?? "",
      topic: options.topic ?? "",
      folder_path: options.folderPath ?? "",
      aggressive_dedup: options.aggressiveDedup ?? false,
      use_semantic_grouping: options.useSemanticGrouping ?? true,
      refine_second_pass: options.refineSecondPass ?? false,
      enrich_with_references: options.enrichWithReferences ?? true,
      use_tag_extraction: options.useTagExtraction ?? false,
      fast_mode: options.fastMode ?? false,
      llm_provider: options.llm?.llm_provider,
      llm_base_url: options.llm?.llm_base_url,
      llm_model: options.llm?.llm_model,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as { filename: string; path: string };
}

export async function uploadSnapshot(
  transcriptFile: string,
  imageBlob: Blob,
): Promise<{ index: number; marker: string }> {
  const form = new FormData();
  form.append("transcript_file", transcriptFile);
  form.append("image", imageBlob, "snapshot.png");
  const res = await fetch(`${BASE}/api/transcripts/snapshots`, {
    method: "POST",
    headers: headers(false),
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as { index: number; marker: string };
}

/** Capture the main study area as PNG for snapshot markers. */
export async function captureMainAreaPng(): Promise<Blob | null> {
  const main = document.querySelector("main");
  if (!main) return null;
  const rect = main.getBoundingClientRect();
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.floor(rect.width));
  canvas.height = Math.max(1, Math.floor(rect.height));
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  try {
    const { default: html2canvas } = await import("html2canvas");
    const shot = await html2canvas(main as HTMLElement, {
      useCORS: true,
      scale: 1,
      logging: false,
    });
    return new Promise((resolve) => shot.toBlob((b) => resolve(b), "image/png"));
  } catch {
    ctx.fillStyle = "#111";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#fff";
    ctx.font = "14px sans-serif";
    ctx.fillText("Snapshot placeholder", 16, 32);
    return new Promise((resolve) => canvas.toBlob((b) => resolve(b), "image/png"));
  }
}

export type { GapAnalysisResult, QuizQuestion, CodeDrill, StudySessionItem, SyncSavedItem };

export async function runGapAnalysis(
  lecturePath: string,
  referencePath: string,
  llm?: LlmOverrides,
): Promise<GapAnalysisResult> {
  const res = await fetch(`${BASE}/api/transcripts/library/gap-analysis`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      lecture_path: lecturePath,
      reference_path: referencePath,
      llm_provider: llm?.llm_provider,
      llm_base_url: llm?.llm_base_url,
      llm_model: llm?.llm_model,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as GapAnalysisResult;
}

export async function generateLibraryQuiz(
  sourcePaths: string[],
  opts?: { count?: number; topic?: string; llm?: LlmOverrides },
): Promise<{
  questions: QuizQuestion[];
  markdown: string;
  session_item: Omit<StudySessionItem, "approved">;
  source?: string;
}> {
  const res = await fetch(`${BASE}/api/transcripts/library/generate-quiz`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      source_paths: sourcePaths,
      count: opts?.count ?? 5,
      topic: opts?.topic ?? "",
      llm_provider: opts?.llm?.llm_provider,
      llm_base_url: opts?.llm?.llm_base_url,
      llm_model: opts?.llm?.llm_model,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as {
    questions: QuizQuestion[];
    markdown: string;
    session_item: Omit<StudySessionItem, "approved">;
    source?: string;
  };
}

export async function generateLibraryDrills(
  sourcePaths: string[],
  opts?: { count?: number; topic?: string; llm?: LlmOverrides },
): Promise<{
  drills: CodeDrill[];
  markdown: string;
  session_item: Omit<StudySessionItem, "approved">;
  source?: string;
}> {
  const res = await fetch(`${BASE}/api/transcripts/library/generate-drills`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      source_paths: sourcePaths,
      count: opts?.count ?? 2,
      topic: opts?.topic ?? "",
      llm_provider: opts?.llm?.llm_provider,
      llm_base_url: opts?.llm?.llm_base_url,
      llm_model: opts?.llm?.llm_model,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as {
    drills: CodeDrill[];
    markdown: string;
    session_item: Omit<StudySessionItem, "approved">;
    source?: string;
  };
}

export async function syncStudySession(
  folderPath: string,
  items: StudySessionItem[],
): Promise<{ saved: SyncSavedItem[]; count: number }> {
  const res = await fetch(`${BASE}/api/transcripts/library/sync-session`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      folder_path: folderPath,
      items: items.map(({ id, kind, title, content, approved, detail: _d }) => ({
        id,
        kind,
        title,
        content,
        approved,
      })),
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as { saved: SyncSavedItem[]; count: number };
}
