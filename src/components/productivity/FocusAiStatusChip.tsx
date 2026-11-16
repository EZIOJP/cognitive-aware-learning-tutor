import { useEffect, useState } from "react";
import {
  FOCUS_LLM_PREFS_EVENT,
  focusLlmStatus,
  loadFocusLlmHostPrefs,
  pingFocusLlmHost,
  saveFocusLlmHostPrefs,
  type FocusLlmStatus,
} from "../../lib/focusLlmHost";
import { cn } from "../../app/components/ui/utils";

type Props = {
  className?: string;
  /** Ping host once on mount (Settings strip). */
  ping?: boolean;
  compact?: boolean;
  /** Click toggles Qwen on/off (Home dashboard). */
  toggleOnClick?: boolean;
};

/**
 * Live Qwen / OpenRouter / Custom indication for Settings + Home.
 */
export function FocusAiStatusChip({
  className = "",
  ping = false,
  compact = false,
  toggleOnClick = false,
}: Props) {
  const [status, setStatus] = useState<FocusLlmStatus>(() => focusLlmStatus());
  const [reach, setReach] = useState<"…" | "up" | "down" | "off">("…");

  useEffect(() => {
    const sync = () => setStatus(focusLlmStatus(loadFocusLlmHostPrefs()));
    sync();
    window.addEventListener(FOCUS_LLM_PREFS_EVENT, sync);
    return () => window.removeEventListener(FOCUS_LLM_PREFS_EVENT, sync);
  }, []);

  const onToggle = () => {
    if (!toggleOnClick) return;
    const cur = loadFocusLlmHostPrefs();
    saveFocusLlmHostPrefs({ ...cur, enabled: !cur.enabled });
  };

  useEffect(() => {
    if (!status.enabled) {
      setReach("off");
      return;
    }
    if (!ping) {
      setReach("…");
      return;
    }
    let cancelled = false;
    setReach("…");
    void pingFocusLlmHost().then((r) => {
      if (!cancelled) setReach(r.ok ? "up" : "down");
    });
    return () => {
      cancelled = true;
    };
  }, [status.enabled, status.preset, status.model, ping]);

  const tone =
    !status.enabled
      ? "text-[#BDB9AE] border-white/10"
      : reach === "up"
        ? "text-[#9FCB8A] border-emerald-400/30 bg-emerald-500/10"
        : reach === "down"
          ? "text-[#E8A07A] border-amber-400/30 bg-amber-500/10"
          : status.preset === "openrouter" && !status.hasKey
            ? "text-[#E8A07A] border-amber-400/25 bg-amber-500/10"
            : "text-sky-100 border-sky-400/25 bg-sky-500/10";

  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={!toggleOnClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px]",
        tone,
        toggleOnClick && "cursor-pointer hover:brightness-110",
        !toggleOnClick && "cursor-default",
        className,
      )}
      title={
        toggleOnClick
          ? status.enabled
            ? "Click to turn Focus AI brain OFF"
            : "Click to turn Focus AI brain ON"
          : status.label
      }
      aria-label={`AI host: ${status.label}`}
    >
      <span className="opacity-70">AI</span>
      <span>{compact ? status.short : status.label}</span>
      {ping && status.enabled ? (
        <span className="opacity-70">
          {reach === "up" ? "· up" : reach === "down" ? "· down" : "· …"}
        </span>
      ) : null}
      {!status.enabled ? <span className="opacity-70">· off</span> : null}
    </button>
  );
}

export default FocusAiStatusChip;
