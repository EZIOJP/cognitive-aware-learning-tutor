/**
 * Focus ↔ OpenJarvis local brain.
 * Uses the same OpenAI-compatible :8000 API as OpenJarvis desktop,
 * plus Ollama :11434 for explicit model warm / unload (keep_alive).
 * SoftLand / Arm / Gate stay native C++.
 */

import { focusLlmHttp } from "./focusLlmNativeHttp";
import {
  FOCUS_LLM_PREFS_EVENT,
  OPENJARVIS_DEFAULT_MODEL,
  OPENJARVIS_HEALTH_URL,
  focusLlmChat,
  focusLlmStatus,
  listOpenJarvisModels,
  loadFocusLlmHostPrefs,
  pickOpenJarvisModel,
  pingOpenJarvisHealth,
  saveFocusLlmHostPrefs,
  syncFocusBrainToOpenJarvis,
  useOpenJarvisAsBrain,
  type FocusLlmHostPrefs,
} from "./focusLlmHost";

const OLLAMA = "http://127.0.0.1:11434";
const BRAIN_PREFS_KEY = "calt:focus-oj-brain:v1";
const PENDING_CLASSIFY_KEY = "calt:focus-classify-pending:v1";

export const FOCUS_OJ_BRAIN_EVENT = "calt:focus-oj-brain-updated";

export type FocusOjBrainPrefs = {
  /** Start `jarvis start` daemon if :8000 is down (no desktop GUI). */
  autoStartServe: boolean;
  /** Warm model before chat/classify. */
  autoLoad: boolean;
  /** Seconds after last use to unload (0 = keep loaded). */
  idleUnloadSec: number;
  /** Keep-alive string sent to Ollama on warm (e.g. 10m). */
  keepAlive: string;
  chatTemperature: number;
  classifyTemperature: number;
  chatMaxTokens: number;
  classifyMaxTokens: number;
};

export const DEFAULT_OJ_BRAIN: FocusOjBrainPrefs = {
  autoStartServe: true,
  autoLoad: true,
  idleUnloadSec: 600,
  keepAlive: "10m",
  chatTemperature: 0.55,
  classifyTemperature: 0.15,
  chatMaxTokens: 512,
  classifyMaxTokens: 400,
};

export const FOCUS_CLASSIFY_CATEGORIES = [
  "IDE / Code Editor",
  "Terminal",
  "Dev Tools",
  "Coding Practice",
  "Study / Reading",
  "Study (Browser)",
  "Coursework (Browser)",
  "AI Tools",
  "AI / ML",
  "AI Assistant",
  "Research",
  "Documentation",
  "Knowledge Work",
  "Office / Docs",
  "File Manager",
  "Gaming",
  "Video Streaming",
  "Video (YouTube)",
  "Music / Media",
  "Social Media",
  "Entertainment",
  "Shopping",
  "Browser",
  "Communication",
  "System",
  "Other",
];

let unloadTimer: number | null = null;
let lastModelUsed = "";

export function loadOjBrainPrefs(): FocusOjBrainPrefs {
  try {
    const raw = localStorage.getItem(BRAIN_PREFS_KEY);
    if (!raw) return { ...DEFAULT_OJ_BRAIN };
    const p = JSON.parse(raw) as Partial<FocusOjBrainPrefs>;
    return {
      autoStartServe:
        typeof p.autoStartServe === "boolean" ? p.autoStartServe : DEFAULT_OJ_BRAIN.autoStartServe,
      autoLoad: typeof p.autoLoad === "boolean" ? p.autoLoad : DEFAULT_OJ_BRAIN.autoLoad,
      idleUnloadSec:
        typeof p.idleUnloadSec === "number" && Number.isFinite(p.idleUnloadSec)
          ? Math.max(0, Math.min(7200, Math.floor(p.idleUnloadSec)))
          : DEFAULT_OJ_BRAIN.idleUnloadSec,
      keepAlive:
        typeof p.keepAlive === "string" && p.keepAlive.trim()
          ? p.keepAlive.trim()
          : DEFAULT_OJ_BRAIN.keepAlive,
      chatTemperature:
        typeof p.chatTemperature === "number"
          ? Math.min(1.2, Math.max(0, p.chatTemperature))
          : DEFAULT_OJ_BRAIN.chatTemperature,
      classifyTemperature:
        typeof p.classifyTemperature === "number"
          ? Math.min(1, Math.max(0, p.classifyTemperature))
          : DEFAULT_OJ_BRAIN.classifyTemperature,
      chatMaxTokens:
        typeof p.chatMaxTokens === "number"
          ? Math.min(2048, Math.max(64, Math.floor(p.chatMaxTokens)))
          : DEFAULT_OJ_BRAIN.chatMaxTokens,
      classifyMaxTokens:
        typeof p.classifyMaxTokens === "number"
          ? Math.min(1024, Math.max(64, Math.floor(p.classifyMaxTokens)))
          : DEFAULT_OJ_BRAIN.classifyMaxTokens,
    };
  } catch {
    return { ...DEFAULT_OJ_BRAIN };
  }
}

export function saveOjBrainPrefs(prefs: FocusOjBrainPrefs): FocusOjBrainPrefs {
  try {
    localStorage.setItem(BRAIN_PREFS_KEY, JSON.stringify(prefs));
    window.dispatchEvent(new CustomEvent(FOCUS_OJ_BRAIN_EVENT, { detail: prefs }));
  } catch {
    /* ignore */
  }
  return prefs;
}

function bumpIdleUnload(model: string) {
  lastModelUsed = model;
  const prefs = loadOjBrainPrefs();
  if (unloadTimer != null) {
    window.clearTimeout(unloadTimer);
    unloadTimer = null;
  }
  if (!prefs.idleUnloadSec) return;
  unloadTimer = window.setTimeout(() => {
    void unloadLocalModel(lastModelUsed || model);
  }, prefs.idleUnloadSec * 1000);
}

/** Ensure OpenJarvis serve is up and Focus prefs point at it. */
export async function ensureOpenJarvisBrain(
  preferredModel?: string,
): Promise<{ ok: boolean; prefs: FocusLlmHostPrefs; detail: string }> {
  const brain = loadOjBrainPrefs();
  const want =
    (preferredModel && preferredModel.trim()) ||
    loadFocusLlmHostPrefs().model ||
    OPENJARVIS_DEFAULT_MODEL;
  if (brain.autoStartServe) {
    const { ensureOpenJarvisServe } = await import("./focusOpenJarvisHost");
    const boot = await ensureOpenJarvisServe(want);
    if (!boot.ok) {
      // Still try sync in case serve came up another way.
      const synced = await syncFocusBrainToOpenJarvis(want);
      return {
        ok: synced.ok,
        prefs: synced.prefs,
        detail: synced.ok ? synced.detail : boot.detail,
      };
    }
  }
  const synced = await syncFocusBrainToOpenJarvis(want);
  return { ok: synced.ok, prefs: synced.prefs, detail: synced.detail };
}

export async function listLoadedOllamaModels(): Promise<string[]> {
  const res = await focusLlmHttp({
    method: "GET",
    url: `${OLLAMA}/api/ps`,
    timeoutMs: 4000,
  });
  if (!res.ok || res.status < 200 || res.status >= 300) return [];
  try {
    const j = JSON.parse(res.body) as { models?: Array<{ name?: string; model?: string }> };
    return (j.models || [])
      .map((m) => String(m.name || m.model || "").trim())
      .filter(Boolean);
  } catch {
    return [];
  }
}

/** Warm model into VRAM via Ollama (same local weights OpenJarvis uses). */
export async function warmLocalModel(
  model?: string,
  keepAlive?: string,
): Promise<{ ok: boolean; model: string; detail: string }> {
  const prefs = loadFocusLlmHostPrefs();
  const brain = loadOjBrainPrefs();
  const m = (model || prefs.model || OPENJARVIS_DEFAULT_MODEL).trim();
  const ka = keepAlive || brain.keepAlive || "10m";
  const res = await focusLlmHttp({
    method: "POST",
    url: `${OLLAMA}/api/chat`,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: m,
      messages: [{ role: "user", content: "ping" }],
      stream: false,
      keep_alive: ka,
      options: { num_predict: 1, temperature: 0 },
    }),
    timeoutMs: 120000,
  });
  if (!res.ok) {
    return { ok: false, model: m, detail: res.error || "warm_failed" };
  }
  if (res.status < 200 || res.status >= 300) {
    return { ok: false, model: m, detail: `warm ${res.status}` };
  }
  bumpIdleUnload(m);
  return { ok: true, model: m, detail: `loaded ${m} keep_alive=${ka}` };
}

/** Unload model from VRAM (Ollama keep_alive: 0). */
export async function unloadLocalModel(
  model?: string,
): Promise<{ ok: boolean; detail: string }> {
  const prefs = loadFocusLlmHostPrefs();
  const m = (model || lastModelUsed || prefs.model || OPENJARVIS_DEFAULT_MODEL).trim();
  const res = await focusLlmHttp({
    method: "POST",
    url: `${OLLAMA}/api/generate`,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: m, keep_alive: 0, prompt: "" }),
    timeoutMs: 30000,
  });
  if (unloadTimer != null) {
    window.clearTimeout(unloadTimer);
    unloadTimer = null;
  }
  if (!res.ok) return { ok: false, detail: res.error || "unload_failed" };
  return {
    ok: res.status >= 200 && res.status < 300,
    detail: res.status >= 200 && res.status < 300 ? `unloaded ${m}` : `unload ${res.status}`,
  };
}

async function prepareModel(model?: string): Promise<string> {
  const brain = loadOjBrainPrefs();
  const host = await ensureOpenJarvisBrain(model);
  const m = host.prefs.model || OPENJARVIS_DEFAULT_MODEL;
  if (brain.autoLoad) {
    const loaded = await listLoadedOllamaModels();
    const already = loaded.some((x) => x === m || x.startsWith(m + ":") || m.startsWith(x));
    if (!already) await warmLocalModel(m, brain.keepAlive);
    else bumpIdleUnload(m);
  } else {
    bumpIdleUnload(m);
  }
  return m;
}

/** Focus-tuned chat via OpenJarvis (native HTTP). */
export async function openJarvisFocusChat(
  messages: Array<{ role: string; content: string }>,
  opts?: { temperature?: number; timeoutMs?: number; maxTokens?: number },
): Promise<{ ok: boolean; text: string; model?: string; error?: string }> {
  const brain = loadOjBrainPrefs();
  await prepareModel();
  // OpenJarvis ChatCompletionRequest supports max_tokens — send via focusLlmChat body.
  // focusLlmChat doesn't pass max_tokens yet; extend call site via raw http if needed.
  const r = await focusLlmChat(messages, {
    temperature: opts?.temperature ?? brain.chatTemperature,
    timeoutMs: opts?.timeoutMs ?? 90000,
  });
  if (r.ok) bumpIdleUnload(r.model || loadFocusLlmHostPrefs().model);
  return r;
}

export type FocusClassifyItem = {
  id: string;
  key: string;
  label: string;
  suggested_category: string;
  confidence: number;
  seconds?: number;
  status: "pending" | "approved" | "rejected";
};

export type FocusClassifyStore = {
  day: string;
  items: FocusClassifyItem[];
  updated_at: string;
};

function localYmd(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function loadFocusClassifyPending(): FocusClassifyStore {
  try {
    const raw = localStorage.getItem(PENDING_CLASSIFY_KEY);
    if (!raw) return { day: localYmd(), items: [], updated_at: "" };
    const s = JSON.parse(raw) as FocusClassifyStore;
    if (s.day !== localYmd()) return { day: localYmd(), items: [], updated_at: "" };
    return {
      day: s.day || localYmd(),
      items: Array.isArray(s.items) ? s.items : [],
      updated_at: s.updated_at || "",
    };
  } catch {
    return { day: localYmd(), items: [], updated_at: "" };
  }
}

export function saveFocusClassifyPending(store: FocusClassifyStore): FocusClassifyStore {
  try {
    localStorage.setItem(PENDING_CLASSIFY_KEY, JSON.stringify(store));
  } catch {
    /* ignore */
  }
  return store;
}

function parseClassifyJson(text: string): Array<{ key: string; category: string; confidence?: number }> {
  const start = text.indexOf("[");
  const end = text.lastIndexOf("]");
  if (start < 0 || end <= start) return [];
  try {
    const arr = JSON.parse(text.slice(start, end + 1)) as unknown;
    if (!Array.isArray(arr)) return [];
    return arr
      .map((row) => {
        const r = row as { key?: string; category?: string; confidence?: number };
        return {
          key: String(r.key || "").trim(),
          category: String(r.category || "").trim(),
          confidence: typeof r.confidence === "number" ? r.confidence : 0.7,
        };
      })
      .filter((r) => r.key && r.category);
  } catch {
    return [];
  }
}

/**
 * Classify uncategorized day_activities via OpenJarvis.
 * Returns pending suggestions (Focus-native, no Study :8000).
 */
export async function scanFocusClassifications(limit = 12): Promise<{
  suggestions: FocusClassifyItem[];
  scanned: number;
  created: number;
  error?: string;
}> {
  const { focusDataUrl } = await import("../utils/focusDataUrl");
  let activities: Array<{
    key?: string;
    label?: string;
    category?: string;
    uncategorized?: boolean;
    seconds?: number;
  }> = [];
  try {
    const res = await fetch(focusDataUrl("day_activities.json"), { cache: "no-store" });
    if (res.ok) {
      const j = (await res.json()) as { activities?: typeof activities };
      activities = Array.isArray(j.activities) ? j.activities : [];
    }
  } catch {
    /* empty */
  }

  const uncat = activities
    .filter(
      (a) =>
        a.uncategorized ||
        !a.category ||
        String(a.category).toLowerCase() === "uncategorized",
    )
    .slice(0, limit);

  if (!uncat.length) {
    const store = loadFocusClassifyPending();
    return {
      suggestions: store.items.filter((i) => i.status === "pending"),
      scanned: 0,
      created: 0,
    };
  }

  await prepareModel();
  const brain = loadOjBrainPrefs();
  const catalog = uncat
    .map(
      (a) =>
        `- key=${a.key || a.label} label=${a.label || a.key} seconds=${a.seconds ?? 0}`,
    )
    .join("\n");
  const cats = FOCUS_CLASSIFY_CATEGORIES.join(", ");
  const r = await focusLlmChat(
    [
      {
        role: "system",
        content:
          "You classify Windows apps/sites for CALT Focus productivity scoring. " +
          "Return ONLY a JSON array of {\"key\":\"...\",\"category\":\"...\",\"confidence\":0-1}. " +
          `Categories must be one of: ${cats}. ` +
          "Use exact key from the list. SoftLand≠Arm. No markdown.",
      },
      {
        role: "user",
        content: `Classify these uncategorized activities:\n${catalog}`,
      },
    ],
    { temperature: brain.classifyTemperature, timeoutMs: 90000 },
  );

  if (!r.ok) {
    return {
      suggestions: loadFocusClassifyPending().items.filter((i) => i.status === "pending"),
      scanned: uncat.length,
      created: 0,
      error: r.error || "classify_failed",
    };
  }

  const parsed = parseClassifyJson(r.text);
  const byKey = new Map(parsed.map((p) => [p.key, p]));
  const store = loadFocusClassifyPending();
  const existing = new Map(store.items.map((i) => [i.key, i]));
  let created = 0;
  for (const a of uncat) {
    const key = String(a.key || a.label || "").trim();
    if (!key) continue;
    const hit = byKey.get(key) || byKey.get(String(a.label || ""));
    if (!hit) continue;
    const prev = existing.get(key);
    if (prev && prev.status !== "pending") continue;
    existing.set(key, {
      id: prev?.id || `fc-${key}-${Date.now()}`,
      key,
      label: String(a.label || key),
      suggested_category: hit.category,
      confidence: Math.min(1, Math.max(0, hit.confidence ?? 0.7)),
      seconds: a.seconds,
      status: "pending",
    });
    created += 1;
  }
  const next: FocusClassifyStore = {
    day: localYmd(),
    items: [...existing.values()],
    updated_at: new Date().toISOString(),
  };
  saveFocusClassifyPending(next);
  bumpIdleUnload(loadFocusLlmHostPrefs().model);
  return {
    suggestions: next.items.filter((i) => i.status === "pending"),
    scanned: uncat.length,
    created,
  };
}

export function markFocusClassifyStatus(
  id: string,
  status: "approved" | "rejected",
  category?: string,
): FocusClassifyItem | null {
  const store = loadFocusClassifyPending();
  const item = store.items.find((i) => i.id === id);
  if (!item) return null;
  item.status = status;
  if (category) item.suggested_category = category;
  saveFocusClassifyPending(store);
  return item;
}

export async function brainStatusLine(): Promise<string> {
  const host = focusLlmStatus(loadFocusLlmHostPrefs());
  const h = await pingOpenJarvisHealth();
  const loaded = await listLoadedOllamaModels();
  const models = h.ok ? await listOpenJarvisModels() : [];
  const pick = pickOpenJarvisModel(models, host.model);
  return [
    host.enabled ? `AI ${host.short}` : "AI off",
    h.ok ? "serve up" : "serve down",
    `model ${pick}`,
    loaded.length ? `vram ${loaded.join(",")}` : "vram empty",
  ].join(" · ");
}

// re-export helpers used by panels
export {
  FOCUS_LLM_PREFS_EVENT,
  listOpenJarvisModels,
  pingOpenJarvisHealth,
  useOpenJarvisAsBrain,
  loadFocusLlmHostPrefs,
  saveFocusLlmHostPrefs,
};
