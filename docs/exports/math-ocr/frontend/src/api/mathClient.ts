import { config } from "../config";

const BASE = config.backend.apiUrl;

const TOKEN_KEY = "vocab:auth-token";

function headers(): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
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
    if (Array.isArray(detail)) {
      return detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ") || `HTTP ${status}`;
    }
  }
  return `HTTP ${status}`;
}

export type MathEvalResult = {
  result: string;
  latex: string;
  steps: string[];
  ok: boolean;
  error?: string | null;
};

export type MathOcrLine = {
  latex: string;
  bbox: { x: number; y: number; w: number; h: number };
  confidence: number;
  structural_confidence: number;
  source: string;
};

export type MathOcrResult = {
  latex: string;
  incomplete_step: boolean;
  confidence: number;
  preprocess_applied: boolean;
  teacher_latex: string;
  needs_review: boolean;
  tier: string;
  lines?: MathOcrLine[];
  structural_confidence?: number;
};

export type MathOcrExtras = {
  paths_json?: string;
  stroke_metrics_json?: string;
  crop_bbox?: { x: number; y: number; w: number; h: number };
  multiline?: boolean;
  ollama_vision_fallback?: boolean;
};

export type TrainPrompt = {
  id: string;
  text: string;
  target_latex: string;
  samples: number;
  target_samples: number;
  remaining: number;
  grid_cells: number;
};

export type TrainTier = {
  id: string;
  label: string;
  samples: number;
  target_samples: number;
  accuracy: number;
  prompts: TrainPrompt[];
};

export type TrainCurriculum = {
  default_target_samples: number;
  tiers: TrainTier[];
  progress: {
    total_samples: number;
    accuracy: number;
    samples_until_retrain: number;
    retrain_threshold: number;
  };
};

export type MathOcrStatus = {
  texteller_available: boolean;
  unimernet_available?: boolean;
  nim_teacher: boolean;
  ollama_vision: boolean;
  tier: string;
  execution_provider?: string | null;
  active_model_id?: string | null;
  finetuned_model?: boolean;
  primary_engine?: string;
  engines?: string[];
};

export type TrainSampleItem = {
  sample_id: string;
  timestamp: string;
  tier: string;
  prompt_id: string;
  prompt_text: string;
  predicted_latex: string;
  confirmed_latex: string;
  teacher_latex: string;
  agree: string;
  png_path: string;
  has_paths_json: boolean;
  has_png: boolean;
  action: string;
  target_latex: string;
  user_id: string;
};

export type TrainSampleList = {
  total: number;
  limit: number;
  offset: number;
  items: TrainSampleItem[];
};

export async function fetchOcrStatus(): Promise<MathOcrStatus | null> {
  try {
    const res = await fetch(`${BASE}/api/math/ocr/status`, { headers: headers() });
    if (!res.ok) return null;
    return (await res.json()) as MathOcrStatus;
  } catch {
    return null;
  }
}

export type TrainSampleResult = {
  sample_id: string;
  confirmed_latex: string;
  teacher_latex: string;
  agree: string;
};

export async function evalMathExpression(expression: string): Promise<MathEvalResult | null> {
  try {
    const res = await fetch(`${BASE}/api/math/eval`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ expression }),
    });
    if (!res.ok) return null;
    return (await res.json()) as MathEvalResult;
  } catch {
    return null;
  }
}

export async function postMathOcr(
  canvas_image: string,
  extras: MathOcrExtras = {}
): Promise<MathOcrResult> {
  const res = await fetch(`${BASE}/api/math/ocr`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ canvas_image, ...extras }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(apiErrorMessage(data, res.status));
  }
  return data as MathOcrResult;
}

export async function fetchTrainCurriculum(): Promise<TrainCurriculum | null> {
  try {
    const res = await fetch(`${BASE}/api/math/train/curriculum`, { headers: headers() });
    if (!res.ok) return null;
    return (await res.json()) as TrainCurriculum;
  } catch {
    return null;
  }
}

export type MathInterventionResult = {
  session_snapshot_id: string;
  latex: string;
  incomplete_step: boolean;
  confidence: number;
  stuckness: number;
  triggered: boolean;
  hint: string;
  question: string;
  detected_concept: string;
  use_llm: boolean;
  structural_confidence?: number;
  tutor_silent?: boolean;
};

export type MathTutorHintResult = {
  hint: string;
  question: string;
  use_llm: boolean;
};

export async function postMathTutorHint(body: {
  canvas_image?: string;
  prompt?: string;
  topic?: string;
  gamma?: number;
  attention?: number;
}): Promise<MathTutorHintResult> {
  const res = await fetch(`${BASE}/api/math/tutor/hint`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(apiErrorMessage(data, res.status));
  }
  return data as MathTutorHintResult;
}

export async function postMathIntervention(body: {
  canvas_image: string;
  paths_json?: string;
  stroke_metrics_json?: string;
  prompt?: string;
  topic?: string;
  gamma?: number;
  attention?: number;
  canvas_idle_seconds?: number;
  eraser_events?: number;
  idle_seconds?: number;
  eraser_strokes?: number;
}): Promise<MathInterventionResult> {
  const res = await fetch(`${BASE}/api/math/intervention`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : `HTTP ${res.status}`);
  }
  return data as MathInterventionResult;
}

export async function patchInterventionRecover(
  snapshotId: string,
  notes = "",
  learnerRecovered = true
): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/api/math/intervention/${snapshotId}/recover`, {
      method: "PATCH",
      headers: headers(),
      body: JSON.stringify({ notes, learner_recovered: learnerRecovered }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function patchInterventionCorrect(
  snapshotId: string,
  correctLatex: string,
  notes = ""
): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/api/math/intervention/${snapshotId}/correct`, {
      method: "PATCH",
      headers: headers(),
      body: JSON.stringify({ correct_latex: correctLatex, notes }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function submitTrainSample(body: {
  tier: string;
  prompt_id: string;
  prompt_text: string;
  canvas_image: string;
  predicted_latex: string;
  confirmed_latex?: string;
  action: "confirm" | "correct";
  paths_json?: string;
  stroke_metrics_json?: string;
  target_latex?: string;
}): Promise<TrainSampleResult | null> {
  try {
    const res = await fetch(`${BASE}/api/math/train/sample`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    return (await res.json()) as TrainSampleResult;
  } catch {
    return null;
  }
}

export async function fetchTrainSamples(opts?: {
  limit?: number;
  offset?: number;
  tier?: string;
  has_paths_json?: boolean;
}): Promise<TrainSampleList | null> {
  try {
    const q = new URLSearchParams();
    if (opts?.limit) q.set("limit", String(opts.limit));
    if (opts?.offset) q.set("offset", String(opts.offset));
    if (opts?.tier) q.set("tier", opts.tier);
    if (opts?.has_paths_json != null) q.set("has_paths_json", String(opts.has_paths_json));
    const res = await fetch(`${BASE}/api/math/train/samples?${q}`, { headers: headers() });
    if (!res.ok) return null;
    return (await res.json()) as TrainSampleList;
  } catch {
    return null;
  }
}

export function trainSampleImageUrl(_sampleId: string): string {
  return "";
}

/** Load PNG with Authorization header (use as img src via blob URL). */
export async function fetchTrainSampleImageBlob(sampleId: string): Promise<string | null> {
  try {
    const res = await fetch(`${BASE}/api/math/train/samples/${sampleId}/image`, {
      headers: headers(),
    });
    if (!res.ok) return null;
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  } catch {
    return null;
  }
}

export async function updateTrainSample(
  sampleId: string,
  body: { confirmed_latex?: string; prompt_text?: string; tier?: string; prompt_id?: string }
): Promise<TrainSampleItem | null> {
  try {
    const res = await fetch(`${BASE}/api/math/train/samples/${sampleId}`, {
      method: "PATCH",
      headers: headers(),
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    return (await res.json()) as TrainSampleItem;
  } catch {
    return null;
  }
}

export async function deleteTrainSample(sampleId: string): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/api/math/train/samples/${sampleId}`, {
      method: "DELETE",
      headers: headers(),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function postRetrainStrokeSymbol(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${BASE}/api/math/train/retrain-stroke-symbol`, {
      method: "POST",
      headers: headers(),
    });
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export async function postRecalibrateStructure(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${BASE}/api/math/train/recalibrate-structure`, {
      method: "POST",
      headers: headers(),
    });
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export async function postRetrainTexteller(mode: "export" | "train" = "export"): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${BASE}/api/math/train/retrain?mode=${mode}`, {
      method: "POST",
      headers: headers(),
    });
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export async function postImportMathwriting(opts?: {
  max_samples?: number;
  skip_duplicates?: boolean;
}): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${BASE}/api/math/train/import`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        max_samples: opts?.max_samples ?? 100,
        skip_duplicates: opts?.skip_duplicates ?? true,
      }),
    });
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export async function fetchTrainDuplicates(): Promise<{ total_groups: number; groups: { key: string; sample_ids: string[]; count: number }[] } | null> {
  try {
    const res = await fetch(`${BASE}/api/math/train/duplicates`, { headers: headers() });
    if (!res.ok) return null;
    return (await res.json()) as { total_groups: number; groups: { key: string; sample_ids: string[]; count: number }[] };
  } catch {
    return null;
  }
}

export async function postTrainDuplicateCleanup(): Promise<{ ok: boolean; deleted: number; groups_cleaned: number } | null> {
  try {
    const res = await fetch(`${BASE}/api/math/train/duplicates/cleanup`, {
      method: "POST",
      headers: headers(),
    });
    if (!res.ok) return null;
    return (await res.json()) as { ok: boolean; deleted: number; groups_cleaned: number };
  } catch {
    return null;
  }
}

export async function postReloadTextellerModel(): Promise<{ model_id: string; finetuned: boolean } | null> {
  try {
    const res = await fetch(`${BASE}/api/math/train/reload-model`, {
      method: "POST",
      headers: headers(),
    });
    if (!res.ok) return null;
    return (await res.json()) as { model_id: string; finetuned: boolean };
  } catch {
    return null;
  }
}
