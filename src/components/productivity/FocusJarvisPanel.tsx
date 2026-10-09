import { useCallback, useEffect, useState } from "react";
import { Loader2, Mic, Send, Volume2 } from "lucide-react";
import { useFocusStatus } from "../../hooks/useFocusStatus";
import {
  FOCUS_JARVIS_PREFS_EVENT,
  jarvisBrief,
  jarvisBriefedToday,
  jarvisSpeak,
  jarvisStop,
  jarvisVoiceLabel,
  listJarvisVoices,
  loadFocusJarvisPrefs,
  markJarvisBriefedToday,
  saveFocusJarvisPrefs,
  whenVoicesReady,
  type FocusJarvisPrefs,
  type JarvisVoiceInfo,
  type JarvisVoiceMode,
} from "../../lib/focusJarvis";
import { runFocusCommand, speakCommandReply } from "../../lib/focusCommands";
import { focusSttAvailable, listenOnceFocus } from "../../lib/focusStt";
import { FocusAiStatusChip } from "./FocusAiStatusChip";
import { loadProductivityGoals } from "./ProductivityGoalsPanel";

type Props = {
  /** Compact Home card vs full Settings panel. */
  variant?: "home" | "settings";
};

const TEST_LINE_JARVIS =
  "Good evening. SoftLand and Arm stay separate. Shall we open a work session?";
const TEST_LINE_NORMAL =
  "Hello. SoftLand and Arm are separate. Ready when you want a work session.";

function buildCtx(status: ReturnType<typeof useFocusStatus>) {
  const goals = loadProductivityGoals();
  const openTodos = [
    ...(status.dayLoop?.tasks || []).filter((t) => !t.done).map((t) => t.title),
    ...goals.extraGoals.filter((g) => !g.done).map((g) => g.title),
  ].slice(0, 6);
  const productive =
    status.dayRollup?.productive_minutes ??
    (status.dayRollup?.productive_seconds != null
      ? Math.floor(status.dayRollup.productive_seconds / 60)
      : status.dayLoop?.tracked_productive_minutes);
  const goalMin =
    typeof status.softland?.goals?.daily_focus_minutes === "number"
      ? Number(status.softland.goals.daily_focus_minutes)
      : status.dayRollup?.daily_focus_minutes;
  const planningEnabled =
    typeof status.dayLoop?.planning_enabled === "boolean"
      ? status.dayLoop.planning_enabled
      : (status.softland?.goals as { planning_enabled?: boolean } | undefined)?.planning_enabled ===
        true;
  return {
    productiveMinutes: typeof productive === "number" ? productive : undefined,
    goalMinutes: typeof goalMin === "number" ? goalMin : undefined,
    bibleDone: Boolean(status.dayLoop?.bible_done),
    planConfirmed: Boolean(status.dayLoop?.plan_confirmed),
    planningEnabled,
    mode: status.softland?.softland_enabled ? "softland" : "off",
    openTodos,
  };
}

function modeDefaults(mode: JarvisVoiceMode): Pick<FocusJarvisPrefs, "rate" | "pitch" | "voiceURI"> {
  if (mode === "normal") return { rate: 1, pitch: 1, voiceURI: "" };
  // Study edge-tts: en-GB-RyanNeural, rate -8%, pitch -2Hz → ~0.92 / 0.88
  return { rate: 0.92, pitch: 0.88, voiceURI: "" };
}

/**
 * Focus-native Jarvis (Study voice_agent spirit): brief + speak via LLM host + speechSynthesis.
 * Voice modes jarvis|normal mirror Study (RyanNeural / JennyNeural) via Edge WebView voices.
 */
export function FocusJarvisPanel({ variant = "settings" }: Props) {
  const status = useFocusStatus();
  const [prefs, setPrefs] = useState<FocusJarvisPrefs>(() => loadFocusJarvisPrefs());
  const [line, setLine] = useState<string | null>(null);
  const [source, setSource] = useState<"llm" | "canned" | "cmd" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voices, setVoices] = useState<JarvisVoiceInfo[]>([]);
  const [cmd, setCmd] = useState("");
  const [listening, setListening] = useState(false);
  const sttOk = focusSttAvailable();

  useEffect(() => {
    const sync = () => setPrefs(loadFocusJarvisPrefs());
    window.addEventListener(FOCUS_JARVIS_PREFS_EVENT, sync);
    return () => window.removeEventListener(FOCUS_JARVIS_PREFS_EVENT, sync);
  }, []);

  useEffect(() => {
    if (variant !== "settings") return;
    let cancelled = false;
    void whenVoicesReady().then((list) => {
      if (!cancelled) setVoices(list);
    });
    const onChange = () => setVoices(listJarvisVoices());
    window.speechSynthesis?.addEventListener("voiceschanged", onChange);
    return () => {
      cancelled = true;
      window.speechSynthesis?.removeEventListener("voiceschanged", onChange);
    };
  }, [variant]);

  const persist = (next: FocusJarvisPrefs) => setPrefs(saveFocusJarvisPrefs(next));

  const setMode = (mode: JarvisVoiceMode) => {
    persist({ ...prefs, voiceMode: mode, ...modeDefaults(mode) });
  };

  const runBrief = useCallback(
    async (mark = false) => {
      if (!prefs.enabled) return;
      setBusy(true);
      setError(null);
      try {
        const r = await jarvisBrief(buildCtx(status));
        setLine(r.line);
        setSource(r.source);
        if (r.error && r.source === "canned") setError(r.error);
        if (r.line) jarvisSpeak(r.line);
        if (mark) markJarvisBriefedToday();
      } finally {
        setBusy(false);
      }
    },
    [prefs.enabled, status],
  );

  const runCmdLine = useCallback(async (rawLine: string) => {
    const raw = rawLine.trim();
    if (!raw) return;
    setBusy(true);
    setError(null);
    try {
      const r = await runFocusCommand(raw);
      setLine(r.reply);
      setSource("cmd");
      if (!r.ok) setError("command");
      speakCommandReply(r);
      setCmd("");
    } finally {
      setBusy(false);
    }
  }, []);

  const runCmd = useCallback(async () => {
    if (busy) return;
    await runCmdLine(cmd);
  }, [busy, cmd, runCmdLine]);

  const listenPtt = useCallback(async () => {
    if (!prefs.enabled || busy || listening) return;
    if (!sttOk) {
      setError("stt");
      setLine("Mic STT unavailable in this WebView — type a command instead.");
      setSource("cmd");
      return;
    }
    setListening(true);
    setError(null);
    setLine("Listening…");
    setSource("cmd");
    try {
      const r = await listenOnceFocus({
        lang: prefs.voiceMode === "jarvis" ? "en-GB" : "en-IN",
        timeoutMs: 9000,
      });
      if (!r.ok || !r.text) {
        setLine(
          r.error === "timeout"
            ? "Didn't catch that — try again."
            : `Listen failed (${r.error || "empty"}).`,
        );
        setError("stt");
        return;
      }
      setCmd(r.text);
      await runCmdLine(r.text);
    } finally {
      setListening(false);
    }
  }, [busy, listening, prefs.enabled, prefs.voiceMode, runCmdLine, sttOk]);

  const commandRow = (
    <form
      className="mt-2 flex gap-1.5"
      onSubmit={(e) => {
        e.preventDefault();
        void runCmd();
      }}
    >
      <input
        type="text"
        value={cmd}
        disabled={!prefs.enabled || busy || listening}
        onChange={(e) => setCmd(e.target.value)}
        placeholder="Command or hold mic — help, brief, status…"
        className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/30 px-2.5 py-1.5 text-[12px] placeholder:text-muted-foreground/70 disabled:opacity-40"
        autoComplete="off"
        spellCheck={false}
      />
      <button
        type="button"
        disabled={!prefs.enabled || busy || listening}
        onClick={() => void listenPtt()}
        title={
          sttOk
            ? "Push-to-talk (Edge speech — Study used faster-whisper when installed)"
            : "STT unavailable"
        }
        className={`inline-flex items-center justify-center rounded-lg border px-2.5 py-1.5 text-[11px] disabled:opacity-40 ${
          listening
            ? "border-rose-400/50 bg-rose-500/20 text-rose-50"
            : "border-white/15 bg-white/5 hover:bg-white/10"
        }`}
        aria-label="Listen"
      >
        {listening ? <Loader2 size={12} className="animate-spin" /> : <Mic size={12} />}
      </button>
      <button
        type="submit"
        disabled={!prefs.enabled || busy || listening || !cmd.trim()}
        className="inline-flex items-center justify-center rounded-lg border border-white/15 bg-white/5 px-2.5 py-1.5 text-[11px] hover:bg-white/10 disabled:opacity-40"
        aria-label="Run command"
      >
        {busy && !listening ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
      </button>
    </form>
  );

  useEffect(() => {
    if (variant !== "home" || !prefs.enabled || !prefs.autoBrief) return;
    if (jarvisBriefedToday()) return;
    void runBrief(true);
  }, [variant, prefs.enabled, prefs.autoBrief, runBrief]);

  if (variant === "home" && !prefs.enabled) return null;

  if (variant === "home") {
    return (
      <section className="gloss-panel rounded-2xl border border-border/40 px-3.5 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Mic size={14} className="text-sky-300/90 shrink-0" aria-hidden />
            <p className="text-[13px] font-medium text-foreground/90">Jarvis</p>
            <span className="text-[10px] text-muted-foreground truncate">
              {prefs.voiceMode === "jarvis" ? "butler" : "normal"}
            </span>
            <FocusAiStatusChip compact />
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => void runBrief(false)}
            className="inline-flex items-center gap-1 rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-[11px] hover:bg-white/10 disabled:opacity-40"
          >
            {busy ? <Loader2 size={12} className="animate-spin" /> : <Volume2 size={12} />}
            Brief
          </button>
        </div>
        {commandRow}
        {line ? (
          <p className="mt-2 text-[13px] leading-relaxed text-sky-50/90 whitespace-pre-wrap">{line}</p>
        ) : (
          <p className="mt-2 text-[11px] text-muted-foreground">
            Type a command (help) or Brief — LLM host for free-text coaching.
          </p>
        )}
        {source ? (
          <p className="mt-1 text-[10px] text-muted-foreground">
            {source === "llm" ? "via LLM host" : source === "cmd" ? "command" : "canned brief"}
          </p>
        ) : null}
      </section>
    );
  }

  const enVoices = voices.filter((v) => /^en/i.test(v.lang) || /English/i.test(v.name));
  const voiceOptions = enVoices.length ? enVoices : voices;

  return (
    <div className="space-y-4">
      <div>
        <h3 className="font-semibold flex items-center gap-2 text-sm">
          <Mic size={16} className="text-primary" />
          Jarvis
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Focus coach + command box + mic. Study used <span className="text-foreground/80">faster-whisper</span>{" "}
          (Python) when installed; Focus listens with Edge Web Speech (same fallback path, no Python
          process). Voice: Jarvis = Ryan / en-GB, Normal = Jenny / en-US. Type{" "}
          <span className="text-foreground/80">help</span> or tap the mic.
        </p>
        <div className="mt-2">
          <FocusAiStatusChip ping />
        </div>
      </div>

      <label className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 px-3 py-2.5 text-sm cursor-pointer">
        <span>
          <span className="block font-medium">Enable Jarvis</span>
          <span className="text-xs text-muted-foreground">Shows on Home; Brief uses LLM host.</span>
        </span>
        <input
          type="checkbox"
          checked={prefs.enabled}
          onChange={(e) => persist({ ...prefs, enabled: e.target.checked })}
        />
      </label>
      <label className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 px-3 py-2.5 text-sm cursor-pointer">
        <span>
          <span className="block font-medium">Speak aloud</span>
          <span className="text-xs text-muted-foreground">{jarvisVoiceLabel(prefs)}</span>
        </span>
        <input
          type="checkbox"
          checked={prefs.speak}
          disabled={!prefs.enabled}
          onChange={(e) => persist({ ...prefs, speak: e.target.checked })}
        />
      </label>
      <label className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 px-3 py-2.5 text-sm cursor-pointer">
        <span>
          <span className="block font-medium">Auto morning brief</span>
          <span className="text-xs text-muted-foreground">Once per day when Home opens.</span>
        </span>
        <input
          type="checkbox"
          checked={prefs.autoBrief}
          disabled={!prefs.enabled}
          onChange={(e) => persist({ ...prefs, autoBrief: e.target.checked })}
        />
      </label>

      <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-3 space-y-3">
        <div>
          <p className="text-sm font-medium">Voice model</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Same jarvis | normal switch as Study voice_agent (RyanNeural / JennyNeural).
          </p>
        </div>
        <div className="flex gap-2">
          {(
            [
              { id: "jarvis" as const, label: "Jarvis", hint: "en-GB Ryan" },
              { id: "normal" as const, label: "Normal", hint: "en-US Jenny" },
            ] as const
          ).map((opt) => {
            const on = prefs.voiceMode === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                disabled={!prefs.enabled}
                onClick={() => setMode(opt.id)}
                className={`flex-1 rounded-lg border px-3 py-2 text-left transition-colors disabled:opacity-40 ${
                  on
                    ? "border-sky-400/50 bg-sky-500/15 text-sky-50"
                    : "border-white/10 bg-white/5 hover:bg-white/10 text-foreground/85"
                }`}
              >
                <span className="block text-sm font-medium">{opt.label}</span>
                <span className="block text-[10px] text-muted-foreground mt-0.5">{opt.hint}</span>
              </button>
            );
          })}
        </div>

        <label className="block space-y-1.5">
          <span className="text-xs text-muted-foreground">Pinned voice (optional)</span>
          <select
            className="w-full rounded-lg border border-white/10 bg-black/40 px-2.5 py-2 text-sm"
            disabled={!prefs.enabled}
            value={prefs.voiceURI}
            onChange={(e) => persist({ ...prefs, voiceURI: e.target.value })}
          >
            <option value="">
              Auto — {prefs.voiceMode === "jarvis" ? "prefer Ryan / en-GB" : "prefer Jenny / en-US"}
            </option>
            {voiceOptions.map((v) => (
              <option key={v.voiceURI} value={v.voiceURI}>
                {v.name} ({v.lang}){v.localService ? "" : " · online"}
              </option>
            ))}
          </select>
          {!voices.length ? (
            <p className="text-[10px] text-amber-200/80">
              No system voices listed yet — Edge may still load Microsoft neural voices shortly.
            </p>
          ) : null}
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="block space-y-1">
            <span className="text-xs text-muted-foreground">Rate {prefs.rate.toFixed(2)}</span>
            <input
              type="range"
              min={0.6}
              max={1.4}
              step={0.02}
              disabled={!prefs.enabled}
              value={prefs.rate}
              onChange={(e) => persist({ ...prefs, rate: Number(e.target.value) })}
              className="w-full"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-xs text-muted-foreground">Pitch {prefs.pitch.toFixed(2)}</span>
            <input
              type="range"
              min={0.6}
              max={1.4}
              step={0.02}
              disabled={!prefs.enabled}
              value={prefs.pitch}
              onChange={(e) => persist({ ...prefs, pitch: Number(e.target.value) })}
              className="w-full"
            />
          </label>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!prefs.enabled}
            onClick={() => {
              jarvisStop();
              jarvisSpeak(
                prefs.voiceMode === "jarvis" ? TEST_LINE_JARVIS : TEST_LINE_NORMAL,
                { force: true },
              );
            }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs hover:bg-white/10 disabled:opacity-50"
          >
            <Volume2 size={13} />
            Test voice
          </button>
          <button
            type="button"
            disabled={!prefs.enabled}
            onClick={() => jarvisStop()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs hover:bg-white/10 disabled:opacity-50"
          >
            Stop
          </button>
        </div>
      </div>

      <div>
        <p className="text-xs text-muted-foreground mb-1.5">Commands</p>
        {commandRow}
      </div>

      <button
        type="button"
        disabled={busy || !prefs.enabled}
        onClick={() => void runBrief(false)}
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs hover:bg-white/10 disabled:opacity-50"
      >
        {busy ? <Loader2 size={13} className="animate-spin" /> : <Volume2 size={13} />}
        Run brief now
      </button>

      {line ? (
        <p className="text-sm text-sky-100/90 leading-relaxed whitespace-pre-wrap">{line}</p>
      ) : null}
      {error ? (
        <p className="text-xs text-amber-200/90">
          {error === "command"
            ? "Command did not succeed"
            : error === "stt"
              ? "Mic / STT issue"
              : `Fallback used (${error})`}
        </p>
      ) : null}
    </div>
  );
}

export default FocusJarvisPanel;
