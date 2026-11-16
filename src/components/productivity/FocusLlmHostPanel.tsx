import { useEffect, useState } from "react";
import { Brain, ExternalLink, Loader2, RefreshCw } from "lucide-react";
import {
  applyLlmPreset,
  FOCUS_LLM_PREFS_EVENT,
  focusLlmStatus,
  loadFocusLlmHostPrefs,
  OPENJARVIS_DEFAULT_MODEL,
  OPENROUTER_DEFAULT_MODEL,
  pingFocusLlmHost,
  QWEN_DEFAULT_MODEL,
  saveFocusLlmHostPrefs,
  type FocusLlmHostPrefs,
  type FocusLlmProviderPreset,
} from "../../lib/focusLlmHost";
import { FocusAiStatusChip } from "./FocusAiStatusChip";

/**
 * Point Focus at OpenJarvis (default) / Ollama / OpenRouter / custom.
 * SoftLand & Arm stay native — this only powers Jarvis chat + session Suggest.
 */
export function FocusLlmHostPanel() {
  const [prefs, setPrefs] = useState<FocusLlmHostPrefs>(() => loadFocusLlmHostPrefs());
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => setPrefs(loadFocusLlmHostPrefs());
    window.addEventListener(FOCUS_LLM_PREFS_EVENT, sync);
    return () => window.removeEventListener(FOCUS_LLM_PREFS_EVENT, sync);
  }, []);

  const persist = (next: FocusLlmHostPrefs) => {
    setPrefs(saveFocusLlmHostPrefs(next));
  };

  const onPreset = (preset: FocusLlmProviderPreset) => {
    const next = applyLlmPreset(preset);
    setPrefs(next);
    setHint(
      preset === "openjarvis"
        ? `OpenJarvis brain — jarvis serve on :8000 (model ${OPENJARVIS_DEFAULT_MODEL}). Local + cloud engines via OpenJarvis config.`
        : preset === "qwen"
          ? `Direct Ollama — ollama serve, then ollama pull ${QWEN_DEFAULT_MODEL}.`
          : preset === "openrouter"
            ? "Direct OpenRouter cloud — paste sk-or-… in Bearer."
            : "Custom OpenAI-compatible /v1 host.",
    );
  };

  const onPing = async () => {
    setBusy(true);
    setHint(null);
    try {
      const r = await pingFocusLlmHost();
      const st = focusLlmStatus();
      setHint(
        r.ok
          ? `${st.short} reachable — ${r.detail}`
          : `${st.short} failed — ${r.detail}${st.preset === "openrouter" && !st.hasKey ? " (add Bearer key)" : ""}`,
      );
    } finally {
      setBusy(false);
    }
  };

  const openRouter = prefs.preset === "openrouter";
  const qwen = prefs.preset === "qwen";
  const openJarvis = prefs.preset === "openjarvis";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold flex items-center gap-2 text-sm">
            <Brain size={16} className="text-primary" />
            Focus AI brain
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Powers Jarvis brief / chat and{" "}
            <strong className="font-medium text-foreground/90">Jarvis</strong> free chat. Default is{" "}
            <strong className="font-medium text-foreground/90">OpenJarvis</strong> (
            <code className="text-[11px]">:8000/v1</code>) — SoftLand/Arm stay native.
          </p>
        </div>
        <FocusAiStatusChip ping />
      </div>

      <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2">
        <div>
          <span className="block text-sm font-medium">Brain on/off</span>
          <span className="text-xs text-muted-foreground">
            Off = heuristics only for Suggest / canned Jarvis lines. Gate Quinn is separate.
          </span>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => persist({ ...prefs, enabled: true })}
            className={`flex-1 rounded-lg border px-3 py-2.5 text-sm font-semibold ${
              prefs.enabled
                ? "border-emerald-400/50 bg-emerald-500/20 text-emerald-50"
                : "border-white/10 bg-white/5 text-muted-foreground hover:bg-white/10"
            }`}
          >
            AI ON
          </button>
          <button
            type="button"
            onClick={() => persist({ ...prefs, enabled: false })}
            className={`flex-1 rounded-lg border px-3 py-2.5 text-sm font-semibold ${
              !prefs.enabled
                ? "border-red-400/50 bg-red-500/20 text-red-50"
                : "border-white/10 bg-white/5 text-muted-foreground hover:bg-white/10"
            }`}
          >
            AI OFF
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {(
          [
            ["openjarvis", "OpenJarvis"],
            ["qwen", "Ollama"],
            ["openrouter", "OpenRouter"],
            ["custom", "Custom"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => onPreset(id)}
            className={`rounded-lg border px-3 py-1.5 text-xs ${
              prefs.preset === id
                ? id === "openrouter"
                  ? "border-violet-400/50 bg-violet-500/15 text-violet-50"
                  : id === "openjarvis"
                    ? "border-sky-400/50 bg-sky-500/15 text-sky-50"
                    : id === "qwen"
                      ? "border-emerald-400/50 bg-emerald-500/15 text-emerald-50"
                      : "border-amber-400/50 bg-amber-500/15 text-amber-50"
                : "border-white/10 bg-white/5 hover:bg-white/10"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {openJarvis ? (
        <div className="rounded-xl border border-sky-400/25 bg-sky-500/10 px-3 py-2.5 text-xs text-sky-50/95 space-y-1.5">
          <p className="font-medium">OpenJarvis (central brain)</p>
          <p className="text-sky-100/75">
            OpenAI-compatible <code className="text-sky-50">http://127.0.0.1:8000/v1</code>. Local
            Ollama models today; cloud engines (NIM / OpenAI / Anthropic) via OpenJarvis config —
            same Focus wire.
          </p>
          <pre className="rounded-lg bg-black/30 px-2 py-1.5 font-mono text-[11px] text-sky-50/90 overflow-x-auto">
            {`jarvis serve --port 8000 --model ${OPENJARVIS_DEFAULT_MODEL} --agent simple`}
          </pre>
          <p className="text-sky-100/60">
            Models we saw working: <code className="text-sky-50">qwen3.5:4b</code>,{" "}
            <code className="text-sky-50">qwen3.5:2b</code>,{" "}
            <code className="text-sky-50">qwen2.5:3b</code>.
          </p>
        </div>
      ) : null}

      {qwen ? (
        <div className="rounded-xl border border-emerald-400/25 bg-emerald-500/10 px-3 py-2.5 text-xs text-emerald-50/95 space-y-1.5">
          <p className="font-medium">Direct Ollama (bypass OpenJarvis)</p>
          <p className="text-emerald-100/75">
            API base <code className="text-emerald-50">http://127.0.0.1:11434/v1</code>.
          </p>
          <pre className="rounded-lg bg-black/30 px-2 py-1.5 font-mono text-[11px] text-emerald-50/90 overflow-x-auto">
            {`ollama pull ${QWEN_DEFAULT_MODEL}\nollama serve`}
          </pre>
        </div>
      ) : null}

      {openRouter ? (
        <div className="rounded-xl border border-violet-400/25 bg-violet-500/10 px-3 py-2.5 text-xs text-violet-50/95 space-y-1.5">
          <p className="font-medium">OpenRouter cloud</p>
          <p className="text-violet-100/75">
            Direct cloud models — e.g.{" "}
            <code className="text-violet-50">{OPENROUTER_DEFAULT_MODEL}</code>. Key from{" "}
            <a
              href="https://openrouter.ai/keys"
              target="_blank"
              rel="noreferrer"
              className="text-violet-200 underline-offset-2 hover:underline"
            >
              openrouter.ai/keys
            </a>
            .
          </p>
          <a
            href="https://openrouter.ai/docs/quickstart"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-violet-200 underline-offset-2 hover:underline"
          >
            Quickstart docs <ExternalLink size={11} />
          </a>
        </div>
      ) : null}

      <div className="grid gap-2 sm:grid-cols-2">
        <label className="block text-xs space-y-1 sm:col-span-2">
          <span className="text-muted-foreground">Base URL (…/v1)</span>
          <input
            value={prefs.baseUrl}
            onChange={(e) => persist({ ...prefs, baseUrl: e.target.value, preset: "custom" })}
            className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm font-mono"
            placeholder={
              openRouter
                ? "https://openrouter.ai/api/v1"
                : openJarvis
                  ? "http://127.0.0.1:8000/v1"
                  : "http://127.0.0.1:11434/v1"
            }
          />
        </label>
        <label className="block text-xs space-y-1">
          <span className="text-muted-foreground">Model</span>
          <input
            value={prefs.model}
            onChange={(e) => persist({ ...prefs, model: e.target.value })}
            className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm font-mono"
            placeholder={
              openRouter
                ? OPENROUTER_DEFAULT_MODEL
                : openJarvis
                  ? OPENJARVIS_DEFAULT_MODEL
                  : QWEN_DEFAULT_MODEL
            }
          />
        </label>
        <label className="block text-xs space-y-1">
          <span className="text-muted-foreground">
            {openRouter ? "OpenRouter API key" : "Bearer (optional)"}
          </span>
          <input
            type="password"
            autoComplete="off"
            value={prefs.apiKey}
            onChange={(e) => persist({ ...prefs, apiKey: e.target.value })}
            className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm font-mono"
            placeholder={openRouter ? "sk-or-v1-…" : "empty for local"}
          />
        </label>
      </div>

      {openRouter && prefs.enabled && !prefs.apiKey.trim() ? (
        <p className="text-xs text-amber-200/90">
          OpenRouter needs a Bearer key for Suggest and Jarvis LLM lines.
        </p>
      ) : null}

      <button
        type="button"
        disabled={busy}
        onClick={() => void onPing()}
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs hover:bg-white/10 disabled:opacity-50"
      >
        {busy ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
        Test host
      </button>

      {hint ? <p className="text-xs text-sky-300">{hint}</p> : null}
      <p className="text-[11px] text-muted-foreground">
        Indication also appears in Settings header and on Home (AI chip + Jarvis). Status lives in
        this browser only — not in the enforcer.
      </p>
    </div>
  );
}

export default FocusLlmHostPanel;
