import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Mic, Send, Trash2, Volume2 } from "lucide-react";
import { useFocusStatus } from "../../hooks/useFocusStatus";
import {
  FOCUS_JARVIS_PREFS_EVENT,
  NVIDIA_VOICES,
  clearJarvisChatTurns,
  jarvisBrief,
  jarvisBriefedToday,
  jarvisSpeak,
  jarvisStop,
  jarvisVoiceLabel,
  listJarvisVoices,
  loadFocusJarvisPrefs,
  loadJarvisChatTurns,
  markJarvisBriefedToday,
  saveFocusJarvisPrefs,
  whenVoicesReady,
  type FocusJarvisPrefs,
  type JarvisChatTurn,
  type JarvisVoiceInfo,
  type JarvisVoiceMode,
} from "../../lib/focusJarvis";
import { runFocusCommand, speakCommandReply } from "../../lib/focusCommands";
import { focusSttAvailable, listenOnceFocus } from "../../lib/focusStt";
import { FocusAiStatusChip } from "./FocusAiStatusChip";
import { FocusQuinnChip } from "./FocusQuinnChip";
import { KarmaOrb } from "./KarmaOrb";
import { loadProductivityGoals } from "./ProductivityGoalsPanel";
import {
  FOCUS_LLM_PREFS_EVENT,
  focusLlmStatus,
  loadFocusLlmHostPrefs,
} from "../../lib/focusLlmHost";
import { brainStatusLine, ensureOpenJarvisBrain } from "../../lib/focusOpenJarvisBrain";

type Props = {
  /** Compact Home card vs full Settings panel. */
  variant?: "home" | "settings";
};

type UiTurn = JarvisChatTurn & { id: string; source?: "llm" | "canned" | "cmd" };

const TEST_LINE_JARVIS =
  "Good evening. SoftLand and Arm stay separate. Bible, then Plan, then Confirm.";
const TEST_LINE_NORMAL =
  "Hello. SoftLand and Arm are separate. Day path is Bible → Plan → Confirm.";
const TEST_LINE_NVIDIA =
  "Good evening. NVIDIA Magpie speech synthesis is online. Bible → Plan → Confirm.";

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
    softlandOn: Boolean(status.softland?.softland_enabled),
  };
}

function modeDefaults(mode: JarvisVoiceMode): Pick<FocusJarvisPrefs, "rate" | "pitch" | "voiceURI"> {
  if (mode === "normal" || mode === "nvidia") return { rate: 1, pitch: 1, voiceURI: "" };
  return { rate: 0.92, pitch: 0.88, voiceURI: "" };
}

function turnsFromStore(): UiTurn[] {
  return loadJarvisChatTurns().map((t, i) => ({
    ...t,
    id: `s-${i}-${t.role}-${t.content.slice(0, 12)}`,
  }));
}

/**
 * Focus-native Jarvis: proper chat transcript + commands + LLM free talk.
 */
export function FocusJarvisPanel({ variant = "settings" }: Props) {
  const status = useFocusStatus();
  const [prefs, setPrefs] = useState<FocusJarvisPrefs>(() => loadFocusJarvisPrefs());
  const [turns, setTurns] = useState<UiTurn[]>(() => turnsFromStore());
  const [busy, setBusy] = useState(false);
  const [voices, setVoices] = useState<JarvisVoiceInfo[]>([]);
  const [cmd, setCmd] = useState("");
  const [listening, setListening] = useState(false);
  const [brainLine, setBrainLine] = useState(() => focusLlmStatus().label);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const sttOk = focusSttAvailable();

  useEffect(() => {
    const sync = () => setPrefs(loadFocusJarvisPrefs());
    window.addEventListener(FOCUS_JARVIS_PREFS_EVENT, sync);
    return () => window.removeEventListener(FOCUS_JARVIS_PREFS_EVENT, sync);
  }, []);

  useEffect(() => {
    const syncBrain = () => setBrainLine(focusLlmStatus(loadFocusLlmHostPrefs()).label);
    syncBrain();
    window.addEventListener(FOCUS_LLM_PREFS_EVENT, syncBrain);
    void ensureOpenJarvisBrain().then(() => {
      void brainStatusLine().then(setBrainLine);
    });
    return () => window.removeEventListener(FOCUS_LLM_PREFS_EVENT, syncBrain);
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

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [turns, busy]);

  const persist = (next: FocusJarvisPrefs) => setPrefs(saveFocusJarvisPrefs(next));

  const setMode = (mode: JarvisVoiceMode) => {
    persist({ ...prefs, voiceMode: mode, ...modeDefaults(mode) });
  };

  const pushPair = (user: string, assistant: string, source: UiTurn["source"]) => {
    setTurns((prev) => {
      const next: UiTurn[] = [
        ...prev,
        { id: `u-${Date.now()}`, role: "user", content: user },
        {
          id: `a-${Date.now() + 1}`,
          role: "assistant",
          content: assistant,
          source,
        },
      ];
      return next.slice(-40);
    });
  };

  const runBrief = useCallback(
    async (mark = false) => {
      if (!prefs.enabled) return;
      setBusy(true);
      try {
        const r = await jarvisBrief(buildCtx(status));
        if (r.line) {
          pushPair("brief", r.line, r.source);
          jarvisSpeak(r.line);
        }
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
    try {
      const r = await runFocusCommand(raw);
      speakCommandReply(r);
      setCmd("");
      // jarvisChat persists turns; commands may not — merge either way.
      const stored = turnsFromStore();
      if (stored.length >= 2) {
        setTurns(stored);
      } else {
        const source: UiTurn["source"] =
          r.source === "llm" ? "llm" : r.source === "canned" ? "canned" : "cmd";
        pushPair(raw, r.reply || (r.ok ? "Done." : "That didn’t work."), source);
      }
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
      pushPair("(mic)", "Mic STT unavailable in this WebView — type instead.", "cmd");
      return;
    }
    setListening(true);
    try {
      const r = await listenOnceFocus({
        lang: prefs.voiceMode === "jarvis" ? "en-GB" : "en-IN",
        timeoutMs: 9000,
      });
      if (!r.ok || !r.text) {
        pushPair(
          "(listen)",
          r.error === "timeout" ? "Didn't catch that — try again." : `Listen failed (${r.error || "empty"}).`,
          "cmd",
        );
        return;
      }
      setCmd(r.text);
      await runCmdLine(r.text);
    } finally {
      setListening(false);
    }
  }, [busy, listening, prefs.enabled, prefs.voiceMode, runCmdLine, sttOk]);

  const clearChat = () => {
    clearJarvisChatTurns();
    setTurns([]);
  };

  const chatTranscript = (
    <div
      ref={scrollerRef}
      className="mt-2 max-h-[min(42vh,22rem)] min-h-[7.5rem] overflow-y-auto rounded-xl border border-white/10 bg-black/25 px-2.5 py-2 space-y-2"
    >
      {turns.length === 0 && !busy ? (
        <p className="text-[11px] text-muted-foreground px-1 py-2">
          Chat with Jarvis here — commands (`help`, `status`, `report`) or free talk when Qwen is on.
        </p>
      ) : null}
      {turns.map((t) => {
        const mine = t.role === "user";
        return (
          <div key={t.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[92%] rounded-2xl px-3 py-1.5 text-[13px] leading-relaxed whitespace-pre-wrap ${
                mine
                  ? "rounded-br-md bg-sky-500/20 text-sky-50 border border-sky-400/25"
                  : "rounded-bl-md bg-white/[0.06] text-foreground/90 border border-white/10"
              }`}
            >
              {!mine ? (
                <span className="block text-[9px] uppercase tracking-wide text-muted-foreground mb-0.5">
                  Jarvis{t.source === "llm" ? " · OpenJarvis" : t.source === "cmd" ? " · cmd" : ""}
                </span>
              ) : null}
              {t.content}
            </div>
          </div>
        );
      })}
      {busy ? (
        <div className="flex justify-start">
          <div className="inline-flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-white/10 bg-white/[0.06] px-3 py-1.5 text-[11px] text-muted-foreground">
            <Loader2 size={12} className="animate-spin" />
            Thinking…
          </div>
        </div>
      ) : null}
    </div>
  );

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
        placeholder="Message OpenJarvis… (or help / classify / load)"
        className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/30 px-2.5 py-1.5 text-[12px] placeholder:text-muted-foreground/70 disabled:opacity-40"
        autoComplete="off"
        spellCheck
      />
      <button
        type="button"
        disabled={!prefs.enabled || busy || listening}
        onClick={() => void listenPtt()}
        title={sttOk ? "Push-to-talk" : "STT unavailable"}
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
        className="inline-flex items-center justify-center rounded-lg border border-sky-400/40 bg-sky-500/15 px-2.5 py-1.5 text-[11px] text-sky-50 hover:bg-sky-500/25 disabled:opacity-40"
        aria-label="Send"
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
            {prefs.karmaOrb ? (
              <KarmaOrb state={busy ? "thinking" : listening ? "listening" : "idle"} onClick={() => void runBrief(false)} />
            ) : null}
            <Mic size={14} className="text-sky-300/90 shrink-0" aria-hidden />
            <p className="text-[13px] font-medium text-foreground/90">Jarvis</p>
            <span className="text-[10px] text-muted-foreground truncate max-w-[10rem]" title={brainLine}>
              {brainLine}
            </span>
            <FocusQuinnChip toggleOnClick />
            <FocusAiStatusChip compact toggleOnClick />
          </div>
          <div className="flex items-center gap-1">
            {turns.length ? (
              <button
                type="button"
                onClick={clearChat}
                className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-muted-foreground hover:bg-white/10"
                title="Clear chat"
              >
                <Trash2 size={11} />
              </button>
            ) : null}
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
        </div>
        {chatTranscript}
        {commandRow}
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
          Local OpenJarvis chat + commands (`model`, `load`, `unload`, `classify`). SoftLand ≠ Arm —
          mutations stay typed commands (`help`).
        </p>
        <div className="mt-2">
          <FocusAiStatusChip ping />
        </div>
      </div>

      <label className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 px-3 py-2.5 text-sm cursor-pointer">
        <span>
          <span className="block font-medium">Enable Jarvis</span>
          <span className="text-xs text-muted-foreground">Shows the Home chat card.</span>
        </span>
        <input
          type="checkbox"
          checked={prefs.enabled}
          onChange={(e) => persist({ ...prefs, enabled: e.target.checked })}
        />
      </label>
      <label className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 px-3 py-2.5 text-sm cursor-pointer">
        <span>
          <span className="block font-medium">Karma Orb</span>
          <span className="text-xs text-muted-foreground">Optional animated orb on the Home Jarvis card. Tap it for a brief.</span>
        </span>
        <input
          type="checkbox"
          checked={prefs.karmaOrb}
          disabled={!prefs.enabled}
          onChange={(e) => persist({ ...prefs, karmaOrb: e.target.checked })}
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
            Jarvis = Ryan / en-GB · Normal = Jenny / en-US · NVIDIA = Magpie Multilingual
          </p>
        </div>
        <div className="flex gap-2">
          {(
            [
              { id: "jarvis" as const, label: "Jarvis", hint: "en-GB Ryan" },
              { id: "normal" as const, label: "Normal", hint: "en-US Jenny" },
              { id: "nvidia" as const, label: "NVIDIA", hint: "Magpie Aria" },
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

        {prefs.voiceMode === "nvidia" ? (
          <div className="space-y-3 pt-1">
            <label className="block space-y-1.5">
              <span className="text-xs text-muted-foreground">NVIDIA voice</span>
              <select
                className="w-full rounded-lg border border-white/10 bg-black/40 px-2.5 py-2 text-sm"
                disabled={!prefs.enabled}
                value={prefs.nvidiaVoice}
                onChange={(e) => persist({ ...prefs, nvidiaVoice: e.target.value })}
              >
                {NVIDIA_VOICES.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="block space-y-1.5">
              <span className="text-xs text-muted-foreground">NVIDIA API Key</span>
              <input
                type="password"
                className="w-full rounded-lg border border-white/10 bg-black/40 px-2.5 py-2 text-sm font-mono placeholder:text-muted-foreground/60"
                disabled={!prefs.enabled}
                value={prefs.nvidiaApiKey}
                placeholder="nvapi-..."
                onChange={(e) => persist({ ...prefs, nvidiaApiKey: e.target.value })}
              />
              <span className="block text-[11px] text-muted-foreground">
                Nemotron Magpie TTS NIM model via NVCF HTTP inference.
              </span>
            </label>
          </div>
        ) : (
          <>
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
          </>
        )}

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!prefs.enabled}
            onClick={() => {
              jarvisStop();
              jarvisSpeak(
                prefs.voiceMode === "jarvis"
                  ? TEST_LINE_JARVIS
                  : prefs.voiceMode === "nvidia"
                    ? TEST_LINE_NVIDIA
                    : TEST_LINE_NORMAL,
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
        <div className="flex items-center justify-between gap-2 mb-1">
          <p className="text-xs text-muted-foreground">Chat</p>
          {turns.length ? (
            <button
              type="button"
              onClick={clearChat}
              className="text-[11px] text-muted-foreground hover:text-foreground"
            >
              Clear
            </button>
          ) : null}
        </div>
        {chatTranscript}
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
    </div>
  );
}

export default FocusJarvisPanel;
