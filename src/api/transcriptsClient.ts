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
    const envelope = data as {
      error?: { message?: string; details?: unknown };
      detail?: unknown;
    };
    const details = envelope.error?.details;
    if (Array.isArray(details) && details.length > 0) {
      const bits = details
        .map((d) => {
          if (!d || typeof d !== "object") return null;
          const row = d as { loc?: unknown[]; msg?: string };
          const loc = Array.isArray(row.loc) ? row.loc.filter((x) => x !== "body").join(".") : "";
          return row.msg ? (loc ? `${loc}: ${row.msg}` : row.msg) : null;
        })
        .filter(Boolean);
      if (bits.length) {
        const base = envelope.error?.message || "Request validation failed";
        return `${base} — ${bits.slice(0, 3).join("; ")}`;
      }
    }
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
  route_profile?: string;
  max_tokens: number;
  reachable: boolean;
  corpus_grounded_notes?: boolean;
  corpus_study_intel?: boolean;
  corpus_available?: boolean;
  default_tier?: string;
  selected_tier?: string;
  tiers?: Record<
    string,
    {
      chain: Array<{ provider: string; model: string; base_url?: string | null }>;
      reachable: boolean;
      budget?: { used: number; cap: number; exceeded: boolean };
    }
  >;
  last_call?: Record<string, unknown> | null;
  last_calls?: LlmCallRecord[];
  task_defaults?: Record<string, string>;
};

export type LlmCallRecord = {
  timestamp?: string;
  task?: string;
  tier?: string;
  route_profile?: string;
  provider?: string | null;
  model?: string | null;
  fallback?: boolean;
  latency_ms?: number;
  error?: string | null;
  prompt_preview?: string | null;
  response_preview?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  generation_id?: string | null;
  upstream_provider?: string | null;
  estimated_cost?: number | null;
  attempts?: Record<string, unknown>[];
};

export type LlmEnvStatus = {
  ollama_enabled: boolean;
  route_profile: string;
  route_profiles?: string[];
  default_tier: string;
  local: { provider: string; base_url: string; model: string };
  keys: Record<string, { configured: boolean; hint: string | null }>;
  allowed_env_keys?: string[];
  task_defaults: Record<string, string>;
};

export type LlmKeysPatch = {
  LLM_CLOUD_API_KEY?: string;
  GEMINI_API_KEY?: string;
  GROQ_API_KEY?: string;
  CEREBRAS_API_KEY?: string;
  MISTRAL_API_KEY?: string;
  GITHUB_TOKEN?: string;
  LLM_OPENROUTER_API_KEY?: string;
  LLM_ANTHROPIC_API_KEY?: string;
  NIM_API_KEY?: string;
  LLM_API_KEY?: string;
  TAVILY_API_KEY?: string;
  LLM_ROUTE_PROFILE?: string;
  OLLAMA_URL?: string;
  LMSTUDIO_URL?: string;
  OLLAMA_NATIVE_URL?: string;
  OLLAMA_MODEL?: string;
  LLM_PROVIDER?: string;
  OLLAMA_ENABLED?: string;
};

export type LlmProbeResult = {
  entry?: string;
  provider?: string;
  model?: string;
  base_url?: string | null;
  configured?: boolean;
  reachable?: boolean;
  latency_ms?: number;
  error?: string | null;
};

export type LlmChainTestResult = {
  tier?: string;
  route_profile?: string;
  task?: string;
  reachable?: boolean;
  entries?: LlmProbeResult[];
};

export type LlmProfileChainTests = {
  tiers: Record<string, LlmChainTestResult>;
  reachable: boolean;
};

export type LlmTestAllProfilesResult = {
  task: string;
  active_profile: string;
  profiles: Record<string, LlmProfileChainTests>;
  summary: { total: number; reachable: number };
};

export type LlmOverrides = {
  llm_provider?: string;
  llm_base_url?: string;
  llm_model?: string;
  llm_tier?: string;
  task_tiers?: Record<string, string>;
  confirm_heavy_budget?: boolean;
};

export function tierForTask(task: string, prefs = loadLlmPrefs()): string | undefined {
  return prefs.task_tiers?.[task] ?? prefs.llm_tier;
}

export function llmBodyFields(llm?: LlmOverrides, confirmHeavyBudget?: boolean) {
  return {
    llm_provider: llm?.llm_provider,
    llm_base_url: llm?.llm_base_url,
    llm_model: llm?.llm_model,
    llm_tier: llm?.llm_tier,
    confirm_heavy_budget: confirmHeavyBudget ?? llm?.confirm_heavy_budget ?? false,
  };
}

export function llmBodyFieldsForTask(
  task: string,
  llm?: LlmOverrides,
  confirmHeavyBudget?: boolean,
) {
  const prefs = llm ?? loadLlmPrefs();
  const tier = tierForTask(task, prefs);
  return llmBodyFields({ ...prefs, llm_tier: tier }, confirmHeavyBudget);
}

const LLM_PREFS_KEY = "lecture-notes:llm";
const LLM_PREFS_MIGRATION_KEY = "lecture-notes:llm-migration-v2";
const LEGACY_TIER_KEY = "lecture-notes:llm-tier";
const VALID_TIERS = new Set(["light", "medium", "heavy"]);

function migrateLegacyTierKey(prefs: LlmOverrides): LlmOverrides {
  if (prefs.llm_tier && VALID_TIERS.has(prefs.llm_tier)) {
    if (localStorage.getItem(LEGACY_TIER_KEY)) {
      localStorage.removeItem(LEGACY_TIER_KEY);
    }
    return prefs;
  }
  const legacyTier = localStorage.getItem(LEGACY_TIER_KEY);
  localStorage.removeItem(LEGACY_TIER_KEY);
  if (legacyTier && VALID_TIERS.has(legacyTier)) {
    const merged = { ...prefs, llm_tier: legacyTier };
    localStorage.setItem(LLM_PREFS_KEY, JSON.stringify(merged));
    return merged;
  }
  return prefs;
}

export function loadLlmPrefs(): LlmOverrides {
  try {
    const raw = localStorage.getItem(LLM_PREFS_KEY);
    let prefs: LlmOverrides = raw ? (JSON.parse(raw) as LlmOverrides) : {};
    if (!localStorage.getItem(LLM_PREFS_MIGRATION_KEY) && prefs.llm_provider === "gemini") {
      prefs = {
        ...prefs,
        llm_provider: "lmstudio",
        llm_base_url: prefs.llm_base_url ?? "http://127.0.0.1:1234",
        llm_model: "google/gemma-4-e4b",
      };
      localStorage.setItem(LLM_PREFS_KEY, JSON.stringify(prefs));
      localStorage.setItem(LLM_PREFS_MIGRATION_KEY, "1");
    }
    return migrateLegacyTierKey(prefs);
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
  if (overrides?.llm_tier) params.set("llm_tier", overrides.llm_tier);
  const qs = params.toString();
  const res = await fetch(`${BASE}/api/transcripts/llm-config${qs ? `?${qs}` : ""}`, {
    headers: headers(),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as LlmConfig;
}

export async function getLlmEnvStatus(): Promise<LlmEnvStatus> {
  const res = await fetch(`${BASE}/api/system/llm/env`, {
    headers: headers(false),
    signal: AbortSignal.timeout(15_000),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as LlmEnvStatus;
}

export async function patchLlmKeys(body: LlmKeysPatch): Promise<{
  written: string[];
  env: LlmEnvStatus;
}> {
  const res = await fetch(`${BASE}/api/system/llm/keys`, {
    method: "PATCH",
    headers: headers(),
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return {
    written: Array.isArray((data as { written?: string[] }).written)
      ? ((data as { written: string[] }).written)
      : [],
    env: (data as { env: LlmEnvStatus }).env,
  };
}

export async function testLlmEntry(body: {
  entry?: string;
  provider?: string;
  model?: string;
  base_url?: string;
  api_key?: string;
}): Promise<LlmProbeResult> {
  const res = await fetch(`${BASE}/api/system/llm/test`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as LlmProbeResult;
}

export async function testLlmChain(body: {
  tier?: string;
  route_profile?: string;
  task?: string;
}): Promise<LlmChainTestResult> {
  const res = await fetch(`${BASE}/api/system/llm/test-chain`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as LlmChainTestResult;
}

export async function testAllRouteProfiles(body?: {
  task?: string;
  profiles?: string[];
}): Promise<LlmTestAllProfilesResult> {
  const res = await fetch(`${BASE}/api/system/llm/test-all-profiles`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body ?? {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  const jobId = (data as { job_id?: string }).job_id;
  if (!jobId) {
    // Legacy sync response (pre-Huey)
    return data as LlmTestAllProfilesResult;
  }
  const deadline = Date.now() + 10 * 60 * 1000;
  while (Date.now() < deadline) {
    const jobRes = await fetch(`${BASE}/api/system/llm/jobs/${encodeURIComponent(jobId)}`, {
      headers: headers(),
    });
    const job = await jobRes.json().catch(() => ({}));
    if (!jobRes.ok) throw new Error(apiErrorMessage(job, jobRes.status));
    const status = (job as { status?: string }).status;
    if (status === "completed" && (job as { result?: LlmTestAllProfilesResult }).result) {
      return (job as { result: LlmTestAllProfilesResult }).result;
    }
    if (status === "failed") {
      throw new Error((job as { error?: string }).error || "Profile matrix test failed");
    }
    await new Promise((r) => setTimeout(r, 800));
  }
  throw new Error(
    "Profile matrix test timed out. Start the Huey worker in another terminal: python -m backend.core.llm_jobs_worker",
  );
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

export async function getNoteContent(
  relativePath: string,
): Promise<{ content: string; mtime?: number }> {
  const encoded = relativePath
    .split("/")
    .map((s) => encodeURIComponent(s))
    .join("/");
  const res = await fetch(`${BASE}/api/transcripts/library/files/${encoded}/content`, {
    headers: headers(),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  const payload = data as { content: string; mtime?: number };
  return { content: payload.content, mtime: payload.mtime };
}

export class NoteConflictError extends Error {
  mtime?: number;
  constructor(message: string, mtime?: number) {
    super(message);
    this.name = "NoteConflictError";
    this.mtime = mtime;
  }
}

export async function saveNoteContent(
  relativePath: string,
  content: string,
  opts?: { expectedMtime?: number | null },
): Promise<{ mtime?: number }> {
  const encoded = relativePath
    .split("/")
    .map((s) => encodeURIComponent(s))
    .join("/");
  const body: { content: string; expected_mtime?: number } = { content };
  if (opts?.expectedMtime != null) body.expected_mtime = opts.expectedMtime;
  const res = await fetch(`${BASE}/api/transcripts/library/files/${encoded}/content`, {
    method: "PUT",
    headers: headers(),
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 409) {
      const detail = (data as { detail?: { message?: string; mtime?: number } | string }).detail;
      const msg =
        typeof detail === "object" && detail?.message
          ? detail.message
          : typeof detail === "string"
            ? detail
            : "This note changed elsewhere. Reload before saving.";
      const mtime =
        typeof detail === "object" && typeof detail?.mtime === "number" ? detail.mtime : undefined;
      throw new NoteConflictError(msg, mtime);
    }
    throw new Error(apiErrorMessage(data, res.status));
  }
  return data as { mtime?: number };
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
      ...llmBodyFieldsForTask("block_regen", opts.llm),
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
      ...llmBodyFieldsForTask("block_regen", opts.llm),
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
      ...llmBodyFieldsForTask("block_regen", opts.llm),
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
      ...llmBodyFieldsForTask("block_regen", opts.llm),
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
      ...llmBodyFieldsForTask("folder_summarize", llm),
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
  enrichVisuals?: boolean;
  forceLegacy?: boolean;
  llm?: LlmOverrides;
  confirmHeavyBudget?: boolean;
};

export async function generateNotes(
  transcriptFile: string,
  options: GenerateNotesOptions = {},
): Promise<{
  filename: string;
  path: string;
  mode?: string;
  grounding_status?: string | null;
  grounding_reason?: string | null;
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
      enrich_visuals: options.enrichVisuals,
      force_legacy: options.forceLegacy ?? true,
      ...llmBodyFieldsForTask("notes_job", options.llm, options.confirmHeavyBudget),
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as {
    filename: string;
    path: string;
    mode?: string;
    corpus_handoff?: { transcript_chunks?: number; note_chunks?: number };
  };
}

export async function generateNotesFromToday(
  options: Omit<GenerateNotesOptions, "referencePaths" | "contextFolder"> = {},
): Promise<{
  filename: string;
  path: string;
  mode?: string;
  grounding_status?: string | null;
  grounding_reason?: string | null;
}> {
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
      enrich_visuals: options.enrichVisuals,
      force_legacy: options.forceLegacy ?? true,
      ...llmBodyFieldsForTask("notes_job", options.llm, options.confirmHeavyBudget),
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as { filename: string; path: string };
}

export async function generatePrimer(
  topic: string,
  options: { folderPath?: string; llm?: LlmOverrides; confirmHeavyBudget?: boolean } = {},
): Promise<{ relative_path: string; title: string; corpus_hits?: number }> {
  const res = await fetch(`${BASE}/api/transcripts/primer`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      topic,
      folder_path: options.folderPath ?? "",
      ...llmBodyFieldsForTask("notes_job", options.llm, options.confirmHeavyBudget),
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as { relative_path: string; title: string; corpus_hits?: number };
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
      ...llmBodyFieldsForTask("gap_analysis", llm),
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as GapAnalysisResult;
}

export async function generateLibraryQuiz(
  sourcePaths: string[],
  opts?: {
    count?: number;
    topic?: string;
    focus?: "mixed" | "concept" | "coding" | "cover_all";
    llm?: LlmOverrides;
    expandSiblings?: boolean;
    save?: boolean;
    folderPath?: string;
  },
): Promise<{
  questions: QuizQuestion[];
  markdown: string;
  session_item: Omit<StudySessionItem, "approved">;
  source?: string;
  focus?: string;
  call_plan?: { role: string; count: number }[];
  sections_covered?: string[];
  saved?: boolean;
  saved_path?: string | null;
  source_paths_used?: string[];
  source_paths_requested?: string[];
  expanded?: boolean;
  llm_calls?: number;
  questions_from_llm?: number;
  questions_from_extractive?: number;
  target_count?: number;
  filled_count?: number;
}> {
  const res = await fetch(`${BASE}/api/transcripts/library/generate-quiz`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      source_paths: sourcePaths,
      count: opts?.count ?? 12,
      topic: opts?.topic ?? "",
      focus: opts?.focus ?? "mixed",
      expand_siblings: opts?.expandSiblings ?? true,
      save: opts?.save,
      folder_path: opts?.folderPath ?? "",
      ...llmBodyFieldsForTask("quiz_gen", opts?.llm),
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as {
    questions: QuizQuestion[];
    markdown: string;
    session_item: Omit<StudySessionItem, "approved">;
    source?: string;
    focus?: string;
    call_plan?: { role: string; count: number }[];
    sections_covered?: string[];
    saved?: boolean;
    saved_path?: string | null;
    source_paths_used?: string[];
    source_paths_requested?: string[];
    expanded?: boolean;
    llm_calls?: number;
    questions_from_llm?: number;
    questions_from_extractive?: number;
    target_count?: number;
    filled_count?: number;
  };
}

export async function pasteLibraryQuiz(
  text: string,
  opts?: { topic?: string },
): Promise<{
  questions: QuizQuestion[];
  markdown: string;
  session_item: Omit<StudySessionItem, "approved">;
  source?: string;
}> {
  const res = await fetch(`${BASE}/api/transcripts/library/paste-quiz`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      text,
      topic: opts?.topic ?? "",
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
      ...llmBodyFieldsForTask("drill_gen", opts?.llm),
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

export type StudyFlowResult = {
  run_id: string | null;
  topic: string;
  steps: {
    retrieve: { hit_count: number };
    notes: { mode: string; relative_path: string; filename: string };
    corpus_handoff: { transcript_chunks?: number; note_chunks?: number };
    quiz: { deck_id: number | null; question_count: number; session_id: string | null };
  };
  next_urls: {
    notes: string;
    quiz: string;
    review_due: string;
  };
};

export async function startTopicStudyFlow(opts: {
  topic: string;
  transcriptFile: string;
  folderPath?: string;
  title?: string;
  ingestCorpus?: boolean;
  quizCount?: number;
  startQuiz?: boolean;
  llm?: LlmOverrides;
  confirmHeavyBudget?: boolean;
}): Promise<StudyFlowResult> {
  const res = await fetch(`${BASE}/api/transcripts/study-flow/start`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      topic: opts.topic,
      transcript_file: opts.transcriptFile,
      folder_path: opts.folderPath ?? "",
      title: opts.title ?? "",
      ingest_corpus: opts.ingestCorpus ?? false,
      quiz_count: opts.quizCount ?? 8,
      start_quiz: opts.startQuiz ?? false,
      ...llmBodyFieldsForTask("notes_job", opts.llm, opts.confirmHeavyBudget),
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data as StudyFlowResult;
}

