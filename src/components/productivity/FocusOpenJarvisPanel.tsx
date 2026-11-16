import { useCallback, useEffect, useState } from "react";
import { ExternalLink, Loader2, Sparkles } from "lucide-react";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import {
  OPENJARVIS_DOCS,
  OPENJARVIS_GITHUB,
  launchOpenJarvisDesktop,
} from "../../lib/focusOpenJarvis";
import {
  FOCUS_LLM_PREFS_EVENT,
  focusLlmStatus,
  listOpenJarvisModels,
  loadFocusLlmHostPrefs,
  OPENJARVIS_DEFAULT_MODEL,
  pickOpenJarvisModel,
  pingOpenJarvisHealth,
  syncFocusBrainToOpenJarvis,
  useOpenJarvisAsBrain,
} from "../../lib/focusLlmHost";
import {
  DEFAULT_OJ_BRAIN,
  FOCUS_OJ_BRAIN_EVENT,
  loadOjBrainPrefs,
  saveOjBrainPrefs,
  unloadLocalModel,
  warmLocalModel,
  type FocusOjBrainPrefs,
} from "../../lib/focusOpenJarvisBrain";

/**
 * OpenJarvis desktop + make it Focus's central AI brain (Suggest / Jarvis chat).
 * SoftLand / Arm / Gate stay native C++.
 */
export function FocusOpenJarvisPanel() {
  const focusShell = isFocusDesktopShell();
  const [hint, setHint] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<"…" | "up" | "down">("…");
  const [models, setModels] = useState<string[]>([]);
  const [brain, setBrain] = useState(() => focusLlmStatus());
  const [ojPrefs, setOjPrefs] = useState<FocusOjBrainPrefs>(() => loadOjBrainPrefs());

  const refresh = useCallback(async () => {
    setHealth("…");
    // Same :8000 API the OpenJarvis desktop chat uses — pick a listed local model.
    const synced = await syncFocusBrainToOpenJarvis();
    setHealth(synced.ok ? "up" : "down");
    if (synced.ok) {
      const list = await listOpenJarvisModels();
      setModels(list);
      setBrain(focusLlmStatus(synced.prefs));
      setHint(
        `Focus AI brain → same OpenJarvis API as this desktop · ${synced.prefs.model}. SoftLand/Arm stay native.`,
      );
    } else {
      setModels([]);
      setBrain(focusLlmStatus(loadFocusLlmHostPrefs()));
      setHint(
        `OpenJarvis API down — ${synced.detail}. Keep jarvis serve on :8000 (model ${OPENJARVIS_DEFAULT_MODEL}).`,
      );
    }
  }, []);

  useEffect(() => {
    void refresh();
    const sync = () => setBrain(focusLlmStatus(loadFocusLlmHostPrefs()));
    const syncOj = () => setOjPrefs(loadOjBrainPrefs());
    window.addEventListener(FOCUS_LLM_PREFS_EVENT, sync);
    window.addEventListener(FOCUS_OJ_BRAIN_EVENT, syncOj);
    return () => {
      window.removeEventListener(FOCUS_LLM_PREFS_EVENT, sync);
      window.removeEventListener(FOCUS_OJ_BRAIN_EVENT, syncOj);
    };
  }, [refresh]);

  const onLaunch = () => {
    if (!focusShell) {
      setHint("Open Focus desktop (calt_focus) to launch the OpenJarvis app.");
      return;
    }
    const ok = launchOpenJarvisDesktop();
    // Desktop app ≠ API; still point Focus at :8000 so chat works once serve is up.
    const next = useOpenJarvisAsBrain();
    setBrain(focusLlmStatus(next));
    setHint(
      ok
        ? "Launching OpenJarvis… Focus AI brain is on (jarvis serve :8000). SoftLand/Arm stay native."
        : "WebView bridge missing — open Focus desktop shell.",
    );
  };

  const onUseAsBrain = async (model?: string) => {
    setBusy(true);
    setHint(null);
    try {
      const h = await pingOpenJarvisHealth();
      if (!h.ok) {
        setHint(
          `OpenJarvis API down — ${h.detail}. In a terminal: jarvis serve --port 8000 --model qwen3.5:4b`,
        );
        setHealth("down");
        return;
      }
      const next = useOpenJarvisAsBrain(model);
      setBrain(focusLlmStatus(next));
      setHealth("up");
      setHint(
        `Focus AI brain → OpenJarvis · ${next.model}. SoftLand/Arm unchanged. Jarvis chat + Suggest use this host.`,
      );
      const list = await listOpenJarvisModels();
      setModels(list);
    } finally {
      setBusy(false);
    }
  };

  const openUrl = (url: string) => {
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const isBrain =
    brain.enabled && brain.preset === "openjarvis" && brain.short === "OpenJarvis";

  return (
    <div className="space-y-3 rounded-xl border border-border/50 bg-background/35 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold flex items-center gap-2 text-sm">
            <Sparkles size={15} className="text-sky-400" />
            OpenJarvis
          </h3>
          <p className="mt-1 text-[11px] text-muted-foreground leading-relaxed max-w-lg">
            Stanford OpenJarvis as Focus&apos;s LLM front door — local Ollama models now; cloud
            engines (NIM / API keys in OpenJarvis config) and OpenRouter preset also available under
            Focus AI brain.
          </p>
        </div>
        <span
          className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
            health === "up"
              ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-100"
              : health === "down"
                ? "border-amber-400/40 bg-amber-500/15 text-amber-100"
                : "border-white/15 text-muted-foreground"
          }`}
        >
          API {health === "…" ? "…" : health}
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => void onUseAsBrain()}
          className={`rounded-lg border px-3 py-2 text-xs font-semibold disabled:opacity-50 ${
            isBrain
              ? "border-emerald-400/50 bg-emerald-500/20 text-emerald-50"
              : "border-sky-400/40 bg-sky-500/15 text-sky-50 hover:bg-sky-500/25"
          }`}
        >
          {busy ? (
            <span className="inline-flex items-center gap-1.5">
              <Loader2 size={12} className="animate-spin" /> Connecting…
            </span>
          ) : isBrain ? (
            `Brain active · ${brain.model}`
          ) : (
            "Use as Focus AI brain"
          )}
        </button>
        <button
          type="button"
          onClick={onLaunch}
          className="rounded-lg border border-border/50 bg-background/40 px-3 py-2 text-xs text-muted-foreground hover:bg-accent/40"
        >
          Open desktop app
        </button>
        <button
          type="button"
          onClick={() => void refresh()}
          className="rounded-lg border border-border/50 bg-background/40 px-3 py-2 text-xs text-muted-foreground hover:bg-accent/40"
        >
          Refresh
        </button>
        <button
          type="button"
          onClick={() => openUrl(OPENJARVIS_DOCS)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border/50 bg-background/40 px-3 py-2 text-xs text-muted-foreground hover:bg-accent/40"
        >
          <ExternalLink size={12} /> Docs
        </button>
        <button
          type="button"
          onClick={() => openUrl(OPENJARVIS_GITHUB)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border/50 bg-background/40 px-3 py-2 text-xs text-muted-foreground hover:bg-accent/40"
        >
          <ExternalLink size={12} /> GitHub
        </button>
      </div>

      {models.length > 0 ? (
        <div className="space-y-1.5">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Models on :8000</p>
          <div className="flex flex-wrap gap-1.5">
            {models.slice(0, 12).map((m) => (
              <button
                key={m}
                type="button"
                disabled={busy}
                onClick={() => void onUseAsBrain(m)}
                className={`rounded-md border px-2 py-1 font-mono text-[10px] ${
                  isBrain && brain.model === m
                    ? "border-sky-400/50 bg-sky-500/20 text-sky-50"
                    : "border-white/10 bg-black/25 text-muted-foreground hover:bg-white/10"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2.5 space-y-2">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Local model (Ollama via OpenJarvis)
        </p>
        <label className="flex items-center justify-between gap-2 text-[11px] cursor-pointer">
          <span>Auto-start API (`jarvis start`, no GUI)</span>
          <input
            type="checkbox"
            checked={ojPrefs.autoStartServe !== false}
            onChange={(e) =>
              setOjPrefs(saveOjBrainPrefs({ ...ojPrefs, autoStartServe: e.target.checked }))
            }
          />
        </label>
        <label className="flex items-center justify-between gap-2 text-[11px] cursor-pointer">
          <span>Auto-load before chat / classify</span>
          <input
            type="checkbox"
            checked={ojPrefs.autoLoad}
            onChange={(e) => setOjPrefs(saveOjBrainPrefs({ ...ojPrefs, autoLoad: e.target.checked }))}
          />
        </label>
        <label className="flex items-center justify-between gap-2 text-[11px]">
          <span>Idle unload (sec, 0=keep)</span>
          <input
            type="number"
            min={0}
            max={7200}
            step={60}
            className="w-20 rounded border border-white/10 bg-black/40 px-1.5 py-0.5 text-right font-mono"
            value={ojPrefs.idleUnloadSec}
            onChange={(e) =>
              setOjPrefs(
                saveOjBrainPrefs({
                  ...ojPrefs,
                  idleUnloadSec: Math.max(0, Math.floor(Number(e.target.value) || 0)),
                }),
              )
            }
          />
        </label>
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void (async () => {
                setBusy(true);
                const { ensureOpenJarvisServe } = await import("../../lib/focusOpenJarvisHost");
                const r = await ensureOpenJarvisServe(brain.model);
                setHealth(r.ok ? "up" : "down");
                setHint(r.ok ? `API started — ${r.detail}` : `Start failed — ${r.detail}`);
                setBusy(false);
              })()
            }
            className="rounded-md border border-sky-400/40 bg-sky-500/15 px-2 py-1 text-[10px] text-sky-50 hover:bg-sky-500/25 disabled:opacity-40"
          >
            Start API
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void (async () => {
                setBusy(true);
                const r = await warmLocalModel(brain.model);
                setHint(r.detail);
                setBusy(false);
              })()
            }
            className="rounded-md border border-white/15 bg-white/5 px-2 py-1 text-[10px] hover:bg-white/10 disabled:opacity-40"
          >
            Load now
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void (async () => {
                setBusy(true);
                const r = await unloadLocalModel(brain.model);
                setHint(r.detail);
                setBusy(false);
              })()
            }
            className="rounded-md border border-white/15 bg-white/5 px-2 py-1 text-[10px] hover:bg-white/10 disabled:opacity-40"
          >
            Unload
          </button>
          <button
            type="button"
            onClick={() => setOjPrefs(saveOjBrainPrefs({ ...DEFAULT_OJ_BRAIN }))}
            className="rounded-md border border-white/15 bg-white/5 px-2 py-1 text-[10px] hover:bg-white/10"
          >
            Reset brain prefs
          </button>
        </div>
      </div>

      {hint ? (
        <p className="text-[11px] text-sky-200/90 leading-relaxed">{hint}</p>
      ) : (
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Keep <code className="text-[10px] bg-black/30 px-1 rounded">jarvis serve --port 8000</code>{" "}
          running. Jarvis chat, Suggest, and Classification use this local brain (native HTTP, no
          CORS). SoftLand/Arm stay C++.
        </p>
      )}
    </div>
  );
}

export default FocusOpenJarvisPanel;
