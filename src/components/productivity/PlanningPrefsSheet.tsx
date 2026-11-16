/**
 * In-gate Planning prefs sheet — stays on Plan tab (no Settings escape).
 */
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { Settings2, X } from "lucide-react";
import {
  closePlanningPrefsSheet,
  openPlanningPrefsSheet,
  PLANNING_PREFS_CLOSE_EVENT,
  PLANNING_PREFS_OPEN_EVENT,
} from "../../lib/planningPrefsSheet";
import { PlanningSettingsPanel } from "./PlanningSettingsPanel";

type Props = {
  refreshKey?: number;
  onPlannerChange?: () => void;
};

export function PlanningPrefsSheet({ refreshKey = 0, onPlannerChange }: Props) {
  const [open, setOpen] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const onOpen = () => setOpen(true);
    const onClose = () => setOpen(false);
    window.addEventListener(PLANNING_PREFS_OPEN_EVENT, onOpen);
    window.addEventListener(PLANNING_PREFS_CLOSE_EVENT, onClose);
    return () => {
      window.removeEventListener(PLANNING_PREFS_OPEN_EVENT, onOpen);
      window.removeEventListener(PLANNING_PREFS_CLOSE_EVENT, onClose);
    };
  }, []);

  // Deep link: ?tab=plan&prefs=1
  useEffect(() => {
    if (searchParams.get("prefs") === "1") {
      setOpen(true);
      const next = new URLSearchParams(searchParams);
      next.delete("prefs");
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-end justify-center sm:items-center p-3 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="planning-prefs-title"
    >
      <button
        type="button"
        className="absolute inset-0 bg-black/55 backdrop-blur-[2px]"
        aria-label="Close planning prefs"
        onClick={() => {
          setOpen(false);
          closePlanningPrefsSheet();
        }}
      />
      <div className="relative z-[1] w-full max-w-lg max-h-[85vh] overflow-y-auto rounded-2xl border border-border/50 bg-background shadow-xl">
        <div className="sticky top-0 z-[1] flex items-center justify-between gap-2 border-b border-border/40 bg-background/95 px-4 py-3 backdrop-blur">
          <div className="flex items-center gap-2 min-w-0">
            <Settings2 size={16} className="text-primary shrink-0" />
            <h2 id="planning-prefs-title" className="text-sm font-semibold truncate">
              Planning prefs
            </h2>
          </div>
          <button
            type="button"
            className="rounded-lg p-1.5 text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            aria-label="Close"
            onClick={() => {
              setOpen(false);
              closePlanningPrefsSheet();
            }}
          >
            <X size={16} />
          </button>
        </div>
        <div className="p-4">
          <p className="mb-3 text-[11px] text-muted-foreground leading-relaxed">
            Bible → Plan → Apply/Confirm. SoftLand and Arm stay out of planning — edit locks later with
            a free day or pass.
          </p>
          <PlanningSettingsPanel
            variant="sheet"
            refreshKey={refreshKey}
            onPlannerChange={onPlannerChange}
          />
        </div>
      </div>
    </div>
  );
}

export function PlanningPrefsGearButton({ className = "" }: { className?: string }) {
  return (
    <button
      type="button"
      onClick={() => openPlanningPrefsSheet()}
      className={
        className ||
        "inline-flex items-center gap-1.5 rounded-lg border border-border/50 bg-background/40 px-2.5 py-1.5 text-xs text-foreground hover:bg-accent/50"
      }
      title="Planning prefs"
    >
      <Settings2 size={13} />
      Prefs
    </button>
  );
}

export default PlanningPrefsSheet;
