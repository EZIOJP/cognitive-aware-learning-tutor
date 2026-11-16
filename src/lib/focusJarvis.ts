/**
 * Focus Jarvis — butler coach (Study voice_agent spirit).
 * Lines from LLM host or canned brief; speak via Web Speech API.
 * Voice modes mirror Study: jarvis (en-GB Ryan-like) | normal (en-US Jenny-like).
 * No Study :8000 / Piper / edge-tts process — WebView2 (Edge) neural voices when installed.
 */

import { ensureFocusLlmBrainOn, loadFocusLlmHostPrefs } from "./focusLlmHost";
import { openJarvisFocusChat } from "./focusOpenJarvisBrain";
import { focusLlmHttp } from "./focusLlmNativeHttp";

const LS_KEY = "calt:focus-jarvis:v1";

export type JarvisVoiceMode = "jarvis" | "normal" | "nvidia";

export const DEFAULT_NVIDIA_TTS_API_KEY =
  "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";

export const DEFAULT_NVIDIA_TTS_URL =
  "https://877104f7-e885-42b9-8de8-f6e4c6303969.invocation.api.nvcf.nvidia.com/v1/audio/synthesize";

export const DEFAULT_NVIDIA_VOICE = "Magpie-Multilingual.EN-US.Aria";

export const NVIDIA_VOICES = [
  { id: "Magpie-Multilingual.EN-US.Aria", name: "Aria (en-US)", lang: "en-US" },
  { id: "Magpie-Multilingual.EN-US.Jason", name: "Jason (en-US)", lang: "en-US" },
  { id: "Magpie-Multilingual.EN-US.Mia", name: "Mia (en-US)", lang: "en-US" },
  { id: "Magpie-Multilingual.EN-US.Leo", name: "Leo (en-US)", lang: "en-US" },
  { id: "Magpie-Multilingual.EN-US.Ray", name: "Ray (en-US)", lang: "en-US" },
  { id: "Magpie-Multilingual.EN-US.Sofia", name: "Sofia (en-US)", lang: "en-US" },
  { id: "Magpie-Multilingual.EN-US.Diego", name: "Diego (en-US)", lang: "en-US" },
  { id: "Magpie-Multilingual.EN-US.Isabela", name: "Isabela (en-US)", lang: "en-US" },
  { id: "Magpie-Multilingual.EN-US.Louise", name: "Louise (en-US)", lang: "en-US" },
  { id: "Magpie-Multilingual.EN-US.Pascal", name: "Pascal (en-US)", lang: "en-US" },
  { id: "Magpie-Multilingual.HI-IN.Siwei", name: "Siwei (hi-IN)", lang: "hi-IN" },
  { id: "Magpie-Multilingual.HI-IN.Leo", name: "Leo (hi-IN)", lang: "hi-IN" },
  { id: "Magpie-Multilingual.HI-IN.Aria", name: "Aria (hi-IN)", lang: "hi-IN" },
  { id: "Magpie-Multilingual.FR-FR.Louise", name: "Louise (fr-FR)", lang: "fr-FR" },
  { id: "Magpie-Multilingual.DE-DE.Pascal", name: "Pascal (de-DE)", lang: "de-DE" },
  { id: "Magpie-Multilingual.ES-US.Isabela", name: "Isabela (es-US)", lang: "es-US" },
  { id: "Magpie-Multilingual.JA-JP.HouZhen", name: "HouZhen (ja-JP)", lang: "ja-JP" },
];

export type FocusJarvisPrefs = {
  enabled: boolean;
  /** Optional compact Karma Orb on the Home Jarvis card. */
  karmaOrb: boolean;
  /** Speak with speechSynthesis or NVIDIA TTS when a line is ready. */
  speak: boolean;
  autoBrief: boolean;
  /** jarvis = British butler (default); normal = plainer US; nvidia = NVIDIA NIM Magpie TTS. */
  voiceMode: JarvisVoiceMode;
  /** Optional pinned speechSynthesis voiceURI; empty = auto-pick for mode. */
  voiceURI: string;
  rate: number;
  pitch: number;
  nvidiaApiKey: string;
  nvidiaVoice: string;
};

export const DEFAULT_JARVIS: FocusJarvisPrefs = {
  enabled: true,
  karmaOrb: false,
  speak: true,
  autoBrief: true,
  voiceMode: "jarvis",
  voiceURI: "",
  rate: 0.92,
  pitch: 0.88,
  nvidiaApiKey: DEFAULT_NVIDIA_TTS_API_KEY,
  nvidiaVoice: DEFAULT_NVIDIA_VOICE,
};

export const FOCUS_JARVIS_PREFS_EVENT = "calt:focus-jarvis-updated";

const JARVIS_VOICE_RE =
  /en-GB|en_GB|United Kingdom|British|Ryan|George|Daniel|Thomas|Oliver|UK English Male|Microsoft Ryan/i;
const NORMAL_VOICE_RE =
  /en-US|en_US|Jenny|Aria|Zira|Guy|United States|US English|Microsoft Jenny|Microsoft Aria/i;

export function loadFocusJarvisPrefs(): FocusJarvisPrefs {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { ...DEFAULT_JARVIS };
    const p = JSON.parse(raw) as Partial<FocusJarvisPrefs>;
    const mode: JarvisVoiceMode =
      p.voiceMode === "nvidia" ? "nvidia" : p.voiceMode === "normal" ? "normal" : "jarvis";
    return {
      enabled: typeof p.enabled === "boolean" ? p.enabled : DEFAULT_JARVIS.enabled,
      karmaOrb: typeof p.karmaOrb === "boolean" ? p.karmaOrb : DEFAULT_JARVIS.karmaOrb,
      speak: typeof p.speak === "boolean" ? p.speak : DEFAULT_JARVIS.speak,
      autoBrief: typeof p.autoBrief === "boolean" ? p.autoBrief : DEFAULT_JARVIS.autoBrief,
      voiceMode: mode,
      voiceURI: typeof p.voiceURI === "string" ? p.voiceURI : "",
      rate:
        typeof p.rate === "number" && Number.isFinite(p.rate)
          ? Math.min(1.4, Math.max(0.6, p.rate))
          : mode === "jarvis"
            ? 0.92
            : 1,
      pitch:
        typeof p.pitch === "number" && Number.isFinite(p.pitch)
          ? Math.min(1.4, Math.max(0.6, p.pitch))
          : mode === "jarvis"
            ? 0.88
            : 1,
      nvidiaApiKey:
        typeof p.nvidiaApiKey === "string" && p.nvidiaApiKey.trim()
          ? p.nvidiaApiKey.trim()
          : DEFAULT_NVIDIA_TTS_API_KEY,
      nvidiaVoice:
        typeof p.nvidiaVoice === "string" && p.nvidiaVoice.trim()
          ? p.nvidiaVoice.trim()
          : DEFAULT_NVIDIA_VOICE,
    };
  } catch {
    return { ...DEFAULT_JARVIS };
  }
}

export function saveFocusJarvisPrefs(prefs: FocusJarvisPrefs): FocusJarvisPrefs {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(prefs));
    window.dispatchEvent(new CustomEvent(FOCUS_JARVIS_PREFS_EVENT, { detail: prefs }));
  } catch {
    /* ignore */
  }
  return prefs;
}

export type JarvisVoiceInfo = {
  name: string;
  lang: string;
  voiceURI: string;
  localService: boolean;
};

/** List browser voices (Edge WebView2 often includes Microsoft neural). */
export function listJarvisVoices(): JarvisVoiceInfo[] {
  if (typeof window === "undefined" || !window.speechSynthesis) return [];
  return window.speechSynthesis.getVoices().map((v) => ({
    name: v.name,
    lang: v.lang,
    voiceURI: v.voiceURI,
    localService: Boolean(v.localService),
  }));
}

/** Wait until voices are loaded (Windows often fires voiceschanged late). */
export function whenVoicesReady(timeoutMs = 2500): Promise<JarvisVoiceInfo[]> {
  return new Promise((resolve) => {
    const ready = () => listJarvisVoices();
    const now = ready();
    if (now.length) {
      resolve(now);
      return;
    }
    if (typeof window === "undefined" || !window.speechSynthesis) {
      resolve([]);
      return;
    }
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      window.speechSynthesis.removeEventListener("voiceschanged", onChange);
      resolve(ready());
    };
    const onChange = () => finish();
    window.speechSynthesis.addEventListener("voiceschanged", onChange);
    window.setTimeout(finish, timeoutMs);
    // Kick Chrome/Edge to populate
    void window.speechSynthesis.getVoices();
  });
}

export function resolveJarvisVoice(
  prefs?: FocusJarvisPrefs,
  voices?: SpeechSynthesisVoice[],
): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !window.speechSynthesis) return null;
  const p = prefs || loadFocusJarvisPrefs();
  const list = voices || window.speechSynthesis.getVoices();
  if (!list.length) return null;

  if (p.voiceURI) {
    const pinned = list.find((v) => v.voiceURI === p.voiceURI);
    if (pinned) return pinned;
  }

  if (p.voiceMode === "normal") {
    return (
      list.find((v) => /Jenny/i.test(v.name)) ||
      list.find((v) => NORMAL_VOICE_RE.test(`${v.name} ${v.lang}`)) ||
      list.find((v) => /^en/i.test(v.lang)) ||
      list[0] ||
      null
    );
  }

  // jarvis — Study default was en-GB-RyanNeural
  return (
    list.find((v) => /Ryan/i.test(v.name) && /en-?GB|United Kingdom/i.test(`${v.lang} ${v.name}`)) ||
    list.find((v) => /Ryan/i.test(v.name)) ||
    list.find((v) => /George|Daniel/i.test(v.name) && /en-?GB/i.test(v.lang)) ||
    list.find((v) => JARVIS_VOICE_RE.test(`${v.name} ${v.lang}`)) ||
    list.find((v) => /en-?GB/i.test(v.lang)) ||
    list.find((v) => /^en/i.test(v.lang)) ||
    list[0] ||
    null
  );
}

export function jarvisVoiceLabel(prefs?: FocusJarvisPrefs): string {
  const p = prefs || loadFocusJarvisPrefs();
  if (p.voiceMode === "nvidia") {
    const v = NVIDIA_VOICES.find((item) => item.id === p.nvidiaVoice);
    return `NVIDIA · ${v ? v.name : (p.nvidiaVoice || "Magpie Aria")}`;
  }
  const v = resolveJarvisVoice(p);
  if (!v) return p.voiceMode === "jarvis" ? "Jarvis · default en-GB" : "Normal · default en-US";
  return `${p.voiceMode === "jarvis" ? "Jarvis" : "Normal"} · ${v.name}`;
}

let currentAudioElement: HTMLAudioElement | null = null;
let currentAudioUrl: string | null = null;

function speakViaSpeechSynthesis(trimmed: string, prefs: FocusJarvisPrefs): void {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  const speakNow = () => {
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(trimmed);
      u.rate = prefs.rate;
      u.pitch = prefs.pitch;
      const voice = resolveJarvisVoice(prefs);
      if (voice) u.voice = voice;
      u.lang = voice?.lang || (prefs.voiceMode === "jarvis" ? "en-GB" : "en-US");
      window.speechSynthesis.speak(u);
    } catch {
      /* ignore */
    }
  };

  if (window.speechSynthesis.getVoices().length) {
    speakNow();
    return;
  }
  void whenVoicesReady().then(() => speakNow());
}

async function speakNvidiaTts(text: string, prefs: FocusJarvisPrefs): Promise<boolean> {
  const apiKey = prefs.nvidiaApiKey || DEFAULT_NVIDIA_TTS_API_KEY;
  const voice = prefs.nvidiaVoice || DEFAULT_NVIDIA_VOICE;
  let lang = "en-US";
  if (voice.includes("HI-IN")) lang = "hi-IN";
  else if (voice.includes("FR-FR")) lang = "fr-FR";
  else if (voice.includes("DE-DE")) lang = "de-DE";
  else if (voice.includes("ES-US")) lang = "es-US";
  else if (voice.includes("JA-JP")) lang = "ja-JP";
  else if (voice.includes("IT-IT")) lang = "it-IT";
  else if (voice.includes("ZH-CN")) lang = "zh-CN";

  const params = new URLSearchParams();
  params.set("text", text);
  params.set("language", lang);
  params.set("voice", voice);
  params.set("encoding", "LINEAR_PCM");
  params.set("sample_rate_hz", "44100");

  const res = await focusLlmHttp({
    method: "POST",
    url: DEFAULT_NVIDIA_TTS_URL,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: params.toString(),
    timeoutMs: 35000,
    base64Response: true,
  });

  if (!res.ok || !res.body) {
    console.warn("NVIDIA TTS synthesis failed:", res.error || res.status);
    return false;
  }

  try {
    jarvisStop();
    const binaryStr = atob(res.body);
    const len = binaryStr.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: "audio/wav" });
    const blobUrl = URL.createObjectURL(blob);
    currentAudioUrl = blobUrl;
    const audio = new Audio(blobUrl);
    currentAudioElement = audio;
    audio.onended = () => {
      if (currentAudioElement === audio) {
        currentAudioElement = null;
      }
      if (currentAudioUrl === blobUrl) {
        URL.revokeObjectURL(blobUrl);
        currentAudioUrl = null;
      }
    };
    audio.onerror = () => {
      if (currentAudioElement === audio) {
        currentAudioElement = null;
      }
    };
    await audio.play();
    return true;
  } catch (err) {
    console.warn("NVIDIA TTS audio playback failed:", err);
    return false;
  }
}

export function jarvisSpeak(text: string, opts?: { force?: boolean }): void {
  const prefs = loadFocusJarvisPrefs();
  if (!opts?.force && (!prefs.enabled || !prefs.speak)) return;
  const trimmed = text.trim().slice(0, 500);
  if (!trimmed) return;

  if (prefs.voiceMode === "nvidia") {
    void speakNvidiaTts(trimmed, prefs).then((ok) => {
      if (!ok) {
        // Fallback to local speech synthesis if offline or error
        speakViaSpeechSynthesis(trimmed, prefs);
      }
    });
    return;
  }

  speakViaSpeechSynthesis(trimmed, prefs);
}

export function jarvisStop(): void {
  try {
    if (currentAudioElement) {
      currentAudioElement.pause();
      currentAudioElement.currentTime = 0;
      currentAudioElement = null;
    }
    if (currentAudioUrl) {
      URL.revokeObjectURL(currentAudioUrl);
      currentAudioUrl = null;
    }
    window.speechSynthesis?.cancel();
  } catch {
    /* ignore */
  }
}

export type JarvisContext = {
  productiveMinutes?: number;
  goalMinutes?: number;
  bibleDone?: boolean;
  planConfirmed?: boolean;
  planningEnabled?: boolean;
  mode?: string;
  openTodos?: string[];
  softlandOn?: boolean;
  armed?: boolean;
};

type ChatTurn = { role: "user" | "assistant"; content: string };
type ChatStore = { day: string; turns: ChatTurn[] };

const CHAT_KEY = "calt:jarvis-chat:v1";
const CHAT_MAX_TURNS = 24;

export type JarvisChatTurn = { role: "user" | "assistant"; content: string };

/** Session chat turns for the Home transcript UI (clears on new local day). */
export function loadJarvisChatTurns(): JarvisChatTurn[] {
  return loadChatStore().turns;
}

export function clearJarvisChatTurns(): void {
  saveChatStore({ day: localYmd(), turns: [] });
}

function loadChatStore(): ChatStore {
  const day = localYmd();
  try {
    const raw = sessionStorage.getItem(CHAT_KEY);
    if (!raw) return { day, turns: [] };
    const p = JSON.parse(raw) as Partial<ChatStore>;
    if (p.day !== day || !Array.isArray(p.turns)) return { day, turns: [] };
    return {
      day,
      turns: p.turns
        .filter(
          (t): t is ChatTurn =>
            !!t &&
            (t.role === "user" || t.role === "assistant") &&
            typeof t.content === "string" &&
            t.content.trim().length > 0,
        )
        .slice(-CHAT_MAX_TURNS),
    };
  } catch {
    return { day, turns: [] };
  }
}

function saveChatStore(store: ChatStore): void {
  try {
    sessionStorage.setItem(CHAT_KEY, JSON.stringify(store));
  } catch {
    /* ignore */
  }
}

function ctxStatusLine(ctx: JarvisContext): string {
  return [
    `bible=${ctx.bibleDone ? "done" : "pending"}`,
    `plan=${ctx.planConfirmed ? "confirmed" : "open"}`,
    `planning=${ctx.planningEnabled !== false}`,
    `productive=${ctx.productiveMinutes ?? 0}m`,
    `goal=${ctx.goalMinutes ?? 0}m`,
    `softland=${ctx.softlandOn ? "on" : "off"}`,
    `arm=${ctx.armed ? "armed" : "off"}`,
    `mode=${ctx.mode || "—"}`,
  ].join("; ");
}

function cannedBrief(ctx: JarvisContext): string {
  const parts: string[] = [];
  const hour = new Date().getHours();
  if (hour < 12) parts.push("Good morning.");
  else if (hour < 18) parts.push("Good afternoon.");
  else parts.push("Good evening.");

  if (!ctx.bibleDone) {
    parts.push("Bible first — then the day opens.");
  } else if (ctx.planningEnabled !== false && !ctx.planConfirmed) {
    parts.push("Confirm today's plan when you're ready.");
  } else {
    parts.push("Day is open. SoftLand and Arm stay separate. Follow today's plan blocks.");
  }

  if (ctx.goalMinutes != null && ctx.goalMinutes > 0) {
    const done = ctx.productiveMinutes ?? 0;
    parts.push(`Focus ${done} of ${ctx.goalMinutes} minutes.`);
  }
  if (ctx.openTodos?.length) {
    parts.push(`Open todos: ${ctx.openTodos.slice(0, 3).join("; ")}.`);
  }
  return parts.join(" ");
}

export async function jarvisBrief(
  ctx: JarvisContext,
): Promise<{ line: string; source: "llm" | "canned"; error?: string }> {
  const prefs = loadFocusJarvisPrefs();
  if (!prefs.enabled) {
    return { line: "", source: "canned", error: "jarvis_off" };
  }
  const fallback = cannedBrief(ctx);
  let llm = loadFocusLlmHostPrefs();
  {
    const { ensureOpenJarvisBrain } = await import("./focusOpenJarvisBrain");
    const synced = await ensureOpenJarvisBrain(llm.model);
    if (synced.ok) llm = synced.prefs;
    else if (!llm.enabled || !llm.baseUrl) llm = ensureFocusLlmBrainOn();
  }
  if (!llm.enabled) {
    return { line: fallback, source: "canned" };
  }
  const r = await openJarvisFocusChat(
    [
      {
        role: "system",
        content:
          "You are Jarvis, a concise British butler for CALT Focus productivity. " +
          "One or two short spoken sentences. No markdown. SoftLand ≠ Arm. " +
          "Prefer Bible → Plan → Apply/Confirm over inventing short sessions. Dry wit, composed.",
      },
      {
        role: "user",
        content: `Morning brief. Mode=${ctx.mode || "—"}; bible=${ctx.bibleDone}; plan=${ctx.planConfirmed}; planning_phase=${ctx.planningEnabled !== false}; productive=${ctx.productiveMinutes ?? 0}m; goal=${ctx.goalMinutes ?? 0}m; todos=${(ctx.openTodos || []).join(", ") || "none"}.`,
      },
    ],
    { temperature: 0.5, timeoutMs: 45000 },
  );
  if (!r.ok || !r.text) {
    return { line: fallback, source: "canned", error: r.error };
  }
  return { line: r.text.replace(/\s+/g, " ").trim(), source: "llm" };
}

/**
 * Free-text coach chat via LLM host. Mutations stay command-only —
 * never claim SoftLand/Arm/unlock changes from chat.
 */
export async function jarvisChat(
  userText: string,
  ctx: JarvisContext = {},
): Promise<{ line: string; source: "llm" | "canned"; error?: string }> {
  const trimmed = userText.trim();
  if (!trimmed) {
    return { line: "", source: "canned", error: "empty" };
  }
  const prefs = loadFocusJarvisPrefs();
  if (!prefs.enabled) {
    return { line: "", source: "canned", error: "jarvis_off" };
  }
  let llm = loadFocusLlmHostPrefs();
  // Auto-start `jarvis start` if needed, then chat via native :8000 (no GUI).
  {
    const { ensureOpenJarvisBrain } = await import("./focusOpenJarvisBrain");
    const synced = await ensureOpenJarvisBrain(llm.model);
    if (synced.ok) llm = synced.prefs;
    else if (!llm.enabled || !llm.baseUrl) llm = ensureFocusLlmBrainOn();
  }
  if (!llm.enabled || !llm.baseUrl) {
    return {
      line: "AI brain still off — open Settings → Advanced → Voice & LLM, or type help.",
      source: "canned",
      error: "llm_disabled",
    };
  }

  const store = loadChatStore();
  const messages: Array<{ role: string; content: string }> = [
    {
      role: "system",
      content:
        "You are Jarvis, a concise British butler coach for CALT Focus. " +
        "Answer the user's question directly (2–5 short sentences unless they ask for more). " +
        "No markdown. SoftLand (browser site block) ≠ Arm (OS process kills). " +
        "You cannot change SoftLand, Arm, rewards, or unlocks — tell them to use typed commands " +
        "(help, softland off UNLOCK, pass) for mutations. Point them to Plan → Confirm when the day is not open. " +
        "Dry wit, composed. Day status follows each user message in brackets.",
    },
  ];
  for (const t of store.turns) {
    messages.push({ role: t.role, content: t.content });
  }
  messages.push({
    role: "user",
    content: `${trimmed}\n\n[status: ${ctxStatusLine(ctx)}]`,
  });

  const r = await openJarvisFocusChat(messages, { temperature: 0.55, timeoutMs: 90000 });
  if (!r.ok || !r.text) {
    const detail = r.error || "unreachable";
    return {
      line:
        detail === "openrouter_no_key"
          ? "OpenRouter needs an API key in Settings → Advanced → Voice & LLM."
          : `OpenJarvis unreachable (${detail}). Type serve to start the API, or help.`,
      source: "canned",
      error: detail,
    };
  }
  const line = r.text.replace(/\s+/g, " ").trim();
  store.turns = [
    ...store.turns,
    { role: "user", content: trimmed },
    { role: "assistant", content: line },
  ].slice(-CHAT_MAX_TURNS);
  store.day = localYmd();
  saveChatStore(store);
  return { line, source: "llm" };
}

const BRIEF_FLAG = "calt:jarvis-briefed:";

export function jarvisBriefedToday(): boolean {
  try {
    return localStorage.getItem(BRIEF_FLAG + localYmd()) === "1";
  } catch {
    return false;
  }
}

export function markJarvisBriefedToday(): void {
  try {
    localStorage.setItem(BRIEF_FLAG + localYmd(), "1");
  } catch {
    /* ignore */
  }
}

function localYmd(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
