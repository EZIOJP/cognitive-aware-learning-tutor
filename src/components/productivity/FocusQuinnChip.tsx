import { useEffect, useState } from "react";
import {
  FOCUS_QUINN_EVENT,
  fetchQuinnDashboardMirror,
  loadFocusQuinnPrefs,
  saveFocusQuinnPrefs,
  type FocusQuinnPrefs,
} from "../../lib/focusQuinn";
import { cn } from "../../app/components/ui/utils";

type Props = {
  className?: string;
  /** Home: click toggles Quinn appeals on/off. */
  toggleOnClick?: boolean;
};

/**
 * Quinn porn-appeal switch for Focus Home.
 * SoftLand blocking stays in Gate; this only gates whether appeals run.
 */
export function FocusQuinnChip({ className = "", toggleOnClick = false }: Props) {
  const [prefs, setPrefs] = useState<FocusQuinnPrefs>(() => loadFocusQuinnPrefs());

  useEffect(() => {
    const sync = () => setPrefs(loadFocusQuinnPrefs());
    sync();
    window.addEventListener(FOCUS_QUINN_EVENT, sync);
    return () => window.removeEventListener(FOCUS_QUINN_EVENT, sync);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void fetchQuinnDashboardMirror().then((m) => {
      if (cancelled || !m) return;
      const cur = loadFocusQuinnPrefs();
      if (cur.appealsEnabled === m.appealsEnabled) return;
      // Hydrate UI from Focus/enforcer mirror without rewriting it.
      setPrefs(saveFocusQuinnPrefs(m, { skipEnforcer: true }));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const on = prefs.appealsEnabled;

  const onToggle = () => {
    if (!toggleOnClick) return;
    saveFocusQuinnPrefs({ appealsEnabled: !on });
  };

  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={!toggleOnClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px]",
        on
          ? "text-emerald-100 border-emerald-400/30 bg-emerald-500/10"
          : "text-[#BDB9AE] border-white/10",
        toggleOnClick && "cursor-pointer hover:brightness-110",
        !toggleOnClick && "cursor-default",
        className,
      )}
      title={
        toggleOnClick
          ? on
            ? "Quinn ON — click to disable porn appeals (blocking stays)"
            : "Quinn OFF — click to allow porn appeals via Qwen"
          : on
            ? "Quinn appeals ON"
            : "Quinn appeals OFF"
      }
      aria-label={on ? "Quinn appeals on" : "Quinn appeals off"}
    >
      <span className="opacity-70">Quinn</span>
      <span>{on ? "ON" : "OFF"}</span>
    </button>
  );
}

export default FocusQuinnChip;
