/**
 * Focus talks to an OpenAI-compatible LLM host.
 * Default brain: OpenJarvis (`jarvis serve` on :8000) — local + optional cloud engines.
 * SoftLand / Arm / Gate stay native C++ (never routed through this host).
 * In calt_focus, HTTP goes through native WinHTTP (WebView CORS blocks :8000 fetch).
 */

import { focusLlmHttp } from "./focusLlmNativeHttp";

const LS_KEY = "calt:focus-llm-host:v1";
export const FOCUS_LLM_PREFS_EVENT = "calt:focus-llm-host-updated";

export type FocusLlmProviderPreset = "openjarvis" | "qwen" | "openrouter" | "custom";

export type FocusLlmHostPrefs = {
  enabled: boolean;
  preset: FocusLlmProviderPreset;
  /** e.g. http://127.0.0.1:8000/v1 (OpenJarvis) or https://openrouter.ai/api/v1 */
  baseUrl: string;
  /** Optional bearer (OpenRouter key, or Ollama if you set one). */
  apiKey: string;
  model: string;
};

/** OpenJarvis OpenAI-compatible server (local models + engines it configures). */
export const OPENJARVIS_DEFAULT_BASE = "http://127.0.0.1:8000/v1";
/** Match the OpenJarvis desktop default that actually answers locally. */
export const OPENJARVIS_DEFAULT_MODEL = "qwen3.5:2b";
export const OPENJARVIS_HEALTH_URL = "http://127.0.0.1:8000/health";

/** Direct Ollama Qwen — no OpenJarvis layer. */
export const QWEN_DEFAULT_MODEL = "qwen2.5:3b";
export const QWEN_DEFAULT_BASE = "http://127.0.0.1:11434/v1";

/** Default OpenRouter slug — swap any id from openrouter.ai/models. */
export const OPENROUTER_DEFAULT_MODEL = "qwen/qwen-2.5-72b-instruct";

export const DEFAULT_FOCUS_LLM: FocusLlmHostPrefs = {
  enabled: true,
  preset: "openjarvis",
  baseUrl: OPENJARVIS_DEFAULT_BASE,
  apiKey: "",
  model: OPENJARVIS_DEFAULT_MODEL,
};

const PRESET_URLS: Record<FocusLlmProviderPreset, string> = {
  openjarvis: OPENJARVIS_DEFAULT_BASE,
  qwen: QWEN_DEFAULT_BASE,
  openrouter: "https://openrouter.ai/api/v1",
  custom: OPENJARVIS_DEFAULT_BASE,
};

function normalizePreset(raw: unknown): FocusLlmProviderPreset {
  if (raw === "openjarvis" || raw === "openrouter" || raw === "custom" || raw === "qwen")
    return raw;
  if (raw === "9router") return "openjarvis";
  return DEFAULT_FOCUS_LLM.preset;
}

function migrateAwayFromNineRouter(prefs: FocusLlmHostPrefs): FocusLlmHostPrefs {
  const url = prefs.baseUrl.trim().toLowerCase();
  const looksLikeNine =
    url.includes(":20128") || url.includes("9router") || prefs.model.startsWith("kr/");
  if (!looksLikeNine) return prefs;
  return {
    ...prefs,
    preset: "openjarvis",
    baseUrl: OPENJARVIS_DEFAULT_BASE,
    model: OPENJARVIS_DEFAULT_MODEL,
  };
}

/** One-time: old default Ollama-only → OpenJarvis when user never customized. */
function migrateDefaultQwenToOpenJarvis(prefs: FocusLlmHostPrefs): FocusLlmHostPrefs {
  if (prefs.preset !== "qwen") return prefs;
  const url = prefs.baseUrl.trim().toLowerCase().replace(/\/$/, "");
  const isStockOllama =
    url === "http://127.0.0.1:11434/v1" || url === "http://localhost:11434/v1";
  const isStockModel =
    !prefs.model.trim() ||
    prefs.model === QWEN_DEFAULT_MODEL ||
    prefs.model === "qwen2.5:3b";
  if (!isStockOllama || !isStockModel) return prefs;
  return {
    ...prefs,
    preset: "openjarvis",
    baseUrl: OPENJARVIS_DEFAULT_BASE,
    model: OPENJARVIS_DEFAULT_MODEL,
  };
}

const REENABLE_OJ_KEY = "calt:focus-llm-host:reenable-oj-v1";

/**
 * One-time: turn the brain back on and point at OpenJarvis.
 * Accidental AI-off left Jarvis / Suggest dead while OpenJarvis looked unused.
 */
function migrateReenableOpenJarvisBrain(prefs: FocusLlmHostPrefs): FocusLlmHostPrefs {
  try {
    if (localStorage.getItem(REENABLE_OJ_KEY) === "1") return prefs;
  } catch {
    return prefs;
  }
  const next: FocusLlmHostPrefs = {
    ...prefs,
    enabled: true,
    preset: prefs.preset === "openrouter" || prefs.preset === "custom" ? prefs.preset : "openjarvis",
    baseUrl:
      prefs.preset === "openrouter" || prefs.preset === "custom"
        ? prefs.baseUrl || OPENJARVIS_DEFAULT_BASE
        : OPENJARVIS_DEFAULT_BASE,
    model:
      prefs.preset === "openrouter" || prefs.preset === "custom"
        ? prefs.model || OPENJARVIS_DEFAULT_MODEL
        : prefs.model?.trim() || OPENJARVIS_DEFAULT_MODEL,
  };
  if (next.preset === "openjarvis") {
    next.baseUrl = OPENJARVIS_DEFAULT_BASE;
    if (!next.model.trim()) next.model = OPENJARVIS_DEFAULT_MODEL;
  }
  try {
    localStorage.setItem(REENABLE_OJ_KEY, "1");
  } catch {
    /* ignore */
  }
  return next;
}

export function loadFocusLlmHostPrefs(): FocusLlmHostPrefs {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { ...DEFAULT_FOCUS_LLM };
    const p = JSON.parse(raw) as Partial<FocusLlmHostPrefs>;
    const loaded: FocusLlmHostPrefs = {
      enabled: typeof p.enabled === "boolean" ? p.enabled : DEFAULT_FOCUS_LLM.enabled,
      preset: normalizePreset(p.preset),
      baseUrl:
        typeof p.baseUrl === "string" && p.baseUrl.trim()
          ? p.baseUrl.trim()
          : DEFAULT_FOCUS_LLM.baseUrl,
      apiKey: typeof p.apiKey === "string" ? p.apiKey : "",
      model:
        typeof p.model === "string" && p.model.trim()
          ? p.model.trim()
          : DEFAULT_FOCUS_LLM.model,
    };
    let next = migrateAwayFromNineRouter(loaded);
    next = migrateDefaultQwenToOpenJarvis(next);
    next = migrateReenableOpenJarvisBrain(next);
    if (
      next.preset !== loaded.preset ||
      next.baseUrl !== loaded.baseUrl ||
      next.model !== loaded.model ||
      next.enabled !== loaded.enabled
    ) {
      try {
        localStorage.setItem(LS_KEY, JSON.stringify(next));
        window.dispatchEvent(new CustomEvent(FOCUS_LLM_PREFS_EVENT, { detail: next }));
      } catch {
        /* ignore */
      }
    }
    return next;
  } catch {
    return { ...DEFAULT_FOCUS_LLM };
  }
}

export function saveFocusLlmHostPrefs(prefs: FocusLlmHostPrefs): FocusLlmHostPrefs {
  const next = { ...prefs, baseUrl: prefs.baseUrl.trim(), model: prefs.model.trim() };
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(next));
    window.dispatchEvent(new CustomEvent(FOCUS_LLM_PREFS_EVENT, { detail: next }));
  } catch {
    /* ignore */
  }
  return next;
}

export type FocusLlmStatus = {
  enabled: boolean;
  preset: FocusLlmProviderPreset;
  label: string;
  short: string;
  hasKey: boolean;
  model: string;
};

/** Compact label for strips / Home (OpenJarvis · Qwen · OpenRouter · off). */
export function focusLlmStatus(prefs?: FocusLlmHostPrefs): FocusLlmStatus {
  const p = prefs || loadFocusLlmHostPrefs();
  if (!p.enabled) {
    return {
      enabled: false,
      preset: p.preset,
      label: "AI off (heuristics)",
      short: "AI off",
      hasKey: Boolean(p.apiKey.trim()),
      model: p.model,
    };
  }
  const name =
    p.preset === "openjarvis"
      ? "OpenJarvis"
      : p.preset === "openrouter"
        ? "OpenRouter"
        : p.preset === "qwen"
          ? "Ollama"
          : "Custom LLM";
  const hasKey = Boolean(p.apiKey.trim());
  return {
    enabled: true,
    preset: p.preset,
    label: `${name}${hasKey ? "" : p.preset === "openrouter" ? " · no key" : ""} · ${p.model}`,
    short: name,
    hasKey,
    model: p.model,
  };
}

function openRouterAttributionHeaders(): Record<string, string> {
  return {
    "HTTP-Referer": "https://calt.focus.local",
    "X-OpenRouter-Title": "CALT Focus",
    "X-Title": "CALT Focus",
  };
}

function authHeaders(prefs: FocusLlmHostPrefs, forJson = false): Record<string, string> {
  const headers: Record<string, string> = {};
  if (forJson) headers["Content-Type"] = "application/json";
  if (prefs.apiKey.trim()) headers.Authorization = `Bearer ${prefs.apiKey.trim()}`;
  if (prefs.preset === "openrouter") Object.assign(headers, openRouterAttributionHeaders());
  return headers;
}

/** Shared OpenAI-compatible chat helper for Suggest + Jarvis. */
export async function focusLlmChat(
  messages: Array<{ role: string; content: string }>,
  opts?: { temperature?: number; timeoutMs?: number },
): Promise<{ ok: boolean; text: string; model?: string; error?: string }> {
  const prefs = loadFocusLlmHostPrefs();
  if (!prefs.enabled || !prefs.baseUrl) {
    return { ok: false, text: "", error: "llm_disabled" };
  }
  if (prefs.preset === "openrouter" && !prefs.apiKey.trim()) {
    return { ok: false, text: "", error: "openrouter_no_key" };
  }
  const url = prefs.baseUrl.replace(/\/$/, "") + "/chat/completions";
  const res = await focusLlmHttp({
    method: "POST",
    url,
    headers: authHeaders(prefs, true),
    body: JSON.stringify({
      model: prefs.model,
      temperature: opts?.temperature ?? 0.4,
      messages,
    }),
    timeoutMs: opts?.timeoutMs ?? 90000,
  });
  if (!res.ok) {
    return { ok: false, text: "", error: res.error || "unreachable" };
  }
  if (res.status < 200 || res.status >= 300) {
    let detail = `host ${res.status}`;
    try {
      const errBody = JSON.parse(res.body) as { error?: { message?: string } | string };
      const msg =
        typeof errBody.error === "string"
          ? errBody.error
          : errBody.error && typeof errBody.error === "object"
            ? errBody.error.message
            : undefined;
      if (msg) detail = `${detail}: ${msg}`;
    } catch {
      /* ignore */
    }
    return { ok: false, text: "", error: detail };
  }
  try {
    const j = JSON.parse(res.body) as {
      choices?: Array<{ message?: { content?: string } }>;
      model?: string;
    };
    const text = (j.choices?.[0]?.message?.content || "").trim();
    return { ok: Boolean(text), text, model: j.model || prefs.model };
  } catch {
    return { ok: false, text: "", error: "bad_llm_json" };
  }
}

export function applyLlmPreset(preset: FocusLlmProviderPreset): FocusLlmHostPrefs {
  const cur = loadFocusLlmHostPrefs();
  const next: FocusLlmHostPrefs = {
    ...cur,
    enabled: true,
    preset,
    baseUrl: PRESET_URLS[preset],
    model:
      preset === "openrouter"
        ? OPENROUTER_DEFAULT_MODEL
        : preset === "openjarvis"
          ? OPENJARVIS_DEFAULT_MODEL
          : preset === "qwen"
            ? QWEN_DEFAULT_MODEL
            : cur.model || OPENJARVIS_DEFAULT_MODEL,
  };
  return saveFocusLlmHostPrefs(next);
}

/** Prefer the model OpenJarvis UI is actually running (2b), else first listed. */
export function pickOpenJarvisModel(available: string[], preferred?: string): string {
  const list = available.map((m) => m.trim()).filter(Boolean);
  const want = (preferred || "").trim();
  if (want && list.includes(want)) return want;
  if (list.includes(OPENJARVIS_DEFAULT_MODEL)) return OPENJARVIS_DEFAULT_MODEL;
  if (list.includes("qwen3.5:4b")) return "qwen3.5:4b";
  if (list.includes("qwen3.5:0.8b")) return "qwen3.5:0.8b";
  return list[0] || want || OPENJARVIS_DEFAULT_MODEL;
}

/** Point Focus AI at OpenJarvis and enable (Jarvis chat + Suggest). */
export function useOpenJarvisAsBrain(model?: string): FocusLlmHostPrefs {
  const cur = loadFocusLlmHostPrefs();
  return saveFocusLlmHostPrefs({
    ...cur,
    enabled: true,
    preset: "openjarvis",
    baseUrl: OPENJARVIS_DEFAULT_BASE,
    model: (model && model.trim()) || OPENJARVIS_DEFAULT_MODEL,
    apiKey: "",
  });
}

/**
 * If the brain is off, turn it on (prefer OpenJarvis). Returns whether prefs changed.
 * SoftLand / Arm / Gate stay native — this only flips the LLM host toggle.
 */
export function ensureFocusLlmBrainOn(): FocusLlmHostPrefs {
  const cur = loadFocusLlmHostPrefs();
  if (cur.enabled && cur.baseUrl.trim()) return cur;
  if (cur.preset === "openrouter" && cur.apiKey.trim()) {
    return saveFocusLlmHostPrefs({ ...cur, enabled: true });
  }
  return useOpenJarvisAsBrain(cur.model);
}

/**
 * Same path the OpenJarvis desktop uses: `jarvis serve` → `/v1/chat/completions`.
 * Enables Focus brain and picks a model that `/v1/models` actually lists.
 */
export async function syncFocusBrainToOpenJarvis(
  preferredModel?: string,
): Promise<{ prefs: FocusLlmHostPrefs; ok: boolean; detail: string }> {
  const h = await pingOpenJarvisHealth();
  if (!h.ok) {
    return {
      prefs: loadFocusLlmHostPrefs(),
      ok: false,
      detail: h.detail,
    };
  }
  const list = await listOpenJarvisModels();
  const cur = loadFocusLlmHostPrefs();
  const model = pickOpenJarvisModel(list, preferredModel || cur.model);
  const prefs = useOpenJarvisAsBrain(model);
  return {
    prefs,
    ok: true,
    detail: list.length
      ? `OpenJarvis · ${model} (${list.length} models)`
      : `OpenJarvis · ${model}`,
  };
}

export async function pingOpenJarvisHealth(): Promise<{ ok: boolean; detail: string }> {
  const res = await focusLlmHttp({
    method: "GET",
    url: OPENJARVIS_HEALTH_URL,
    timeoutMs: 4000,
  });
  if (!res.ok) {
    return {
      ok: false,
      detail: res.error || "unreachable — start jarvis serve --port 8000",
    };
  }
  if (res.status < 200 || res.status >= 300) {
    return { ok: false, detail: `health ${res.status}` };
  }
  return { ok: true, detail: "OpenJarvis serve ok" };
}

export async function listOpenJarvisModels(): Promise<string[]> {
  const res = await focusLlmHttp({
    method: "GET",
    url: `${OPENJARVIS_DEFAULT_BASE}/models`,
    timeoutMs: 8000,
  });
  if (!res.ok || res.status < 200 || res.status >= 300) return [];
  try {
    const j = JSON.parse(res.body) as { data?: Array<{ id?: string }> };
    return (j.data || []).map((m) => String(m.id || "")).filter(Boolean);
  } catch {
    return [];
  }
}

export type SessionSuggestChip = {
  kind: "app" | "site";
  id: string;
  label: string;
  seconds?: number;
};

export type SessionSuggestResult = {
  allow_apps: string[];
  allow_sites: string[];
  block_apps: string[];
  source: "llm" | "heuristic";
  model?: string;
  error?: string;
};

function heuristicSuggest(chips: SessionSuggestChip[]): SessionSuggestResult {
  const PRODUCTIVE = new Set([
    "cursor.exe",
    "code.exe",
    "winword.exe",
    "excel.exe",
    "notion.exe",
    "obsidian.exe",
    "slack.exe",
    "teams.exe",
    "figma.exe",
    "onenote.exe",
  ]);
  const DISTRACT = new Set([
    "steam.exe",
    "steamwebhelper.exe",
    "discord.exe",
    "discordptb.exe",
    "spotify.exe",
    "robloxplayerbeta.exe",
    "valorant.exe",
    "leagueclient.exe",
    "epicgameslauncher.exe",
    "netflix.exe",
    "mhur.exe",
  ]);
  const allow_apps: string[] = [];
  const allow_sites: string[] = [];
  const block_apps: string[] = [];
  for (const c of chips) {
    if (c.kind === "site") {
      allow_sites.push(c.id);
      continue;
    }
    if (DISTRACT.has(c.id)) block_apps.push(c.id);
    else if (PRODUCTIVE.has(c.id)) allow_apps.push(c.id);
    else if ((c.seconds || 0) > 0) allow_apps.push(c.id);
  }
  return { allow_apps, allow_sites, block_apps, source: "heuristic" };
}

function parseSuggestJson(text: string): Partial<SessionSuggestResult> | null {
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start < 0 || end <= start) return null;
  try {
    return JSON.parse(text.slice(start, end + 1)) as Partial<SessionSuggestResult>;
  } catch {
    return null;
  }
}

/** Ask the hosted LLM to sort chips into allow/block. Falls back to heuristics. */
export async function suggestSessionLists(
  chips: SessionSuggestChip[],
): Promise<SessionSuggestResult> {
  const prefs = loadFocusLlmHostPrefs();
  const fallback = heuristicSuggest(chips);
  if (!prefs.enabled || !prefs.baseUrl) return fallback;

  const catalog = chips
    .slice(0, 40)
    .map(
      (c) =>
        `- ${c.kind}:${c.id} (${c.label}${c.seconds != null ? `, ${Math.round(c.seconds / 60)}m` : ""})`,
    )
    .join("\n");

  // Warm OpenJarvis/Ollama then classify (same local path as desktop chat).
  const { openJarvisFocusChat } = await import("./focusOpenJarvisBrain");
  const r = await openJarvisFocusChat(
    [
      {
        role: "system",
        content:
          "You help CALT Focus work sessions. Given used apps/sites, return ONLY JSON: " +
          '{"allow_apps":["exe"],"allow_sites":["host"],"block_apps":["exe"]}. ' +
          "Allow = productive for a focus session. Block = games/social distraction (Arm kill list). " +
          "Sites go only in allow_sites. Use exact ids from the list. No markdown.",
      },
      {
        role: "user",
        content: `Sort these for a focus work session:\n${catalog}`,
      },
    ],
    { temperature: 0.15, timeoutMs: 90000 },
  );
  if (!r.ok) return { ...fallback, error: r.error || "host_unreachable" };
  const parsed = parseSuggestJson(r.text);
  if (!parsed) return { ...fallback, error: "bad_llm_json" };
  return {
    allow_apps: Array.isArray(parsed.allow_apps) ? parsed.allow_apps.map(String) : fallback.allow_apps,
    allow_sites: Array.isArray(parsed.allow_sites)
      ? parsed.allow_sites.map(String)
      : fallback.allow_sites,
    block_apps: Array.isArray(parsed.block_apps) ? parsed.block_apps.map(String) : fallback.block_apps,
    source: "llm",
    model: r.model || prefs.model,
  };
}

export async function pingFocusLlmHost(): Promise<{ ok: boolean; detail: string }> {
  const prefs = loadFocusLlmHostPrefs();
  if (prefs.preset === "openrouter" && !prefs.apiKey.trim()) {
    return { ok: false, detail: "OpenRouter needs a Bearer key (openrouter.ai/keys)" };
  }
  if (prefs.preset === "openjarvis") {
    const h = await pingOpenJarvisHealth();
    if (!h.ok) {
      return {
        ok: false,
        detail: `${h.detail} — run: jarvis serve --port 8000 --model ${prefs.model || OPENJARVIS_DEFAULT_MODEL}`,
      };
    }
  }
  const base = prefs.baseUrl.replace(/\/$/, "");
  const res = await focusLlmHttp({
    method: "GET",
    url: base + "/models",
    headers: authHeaders(prefs),
    timeoutMs: 8000,
  });
  if (res.ok && res.status >= 200 && res.status < 300) {
    return { ok: true, detail: `models ok (${res.status})` };
  }
  if (res.ok) {
    return { ok: res.status < 500, detail: `HTTP ${res.status} on /models` };
  }
  {
    const msg = res.error || "unreachable";
    if (prefs.preset === "openjarvis") {
      return {
        ok: false,
        detail: `${msg} — start OpenJarvis API: jarvis serve --port 8000`,
      };
    }
    if (prefs.preset === "qwen") {
      return {
        ok: false,
        detail: `${msg} — start Ollama and run: ollama pull ${prefs.model || QWEN_DEFAULT_MODEL}`,
      };
    }
    return { ok: false, detail: msg };
  }
}
