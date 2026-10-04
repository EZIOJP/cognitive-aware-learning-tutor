import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { useFocusStatus } from "../../hooks/useFocusStatus";
import { invalidateFocusStatusBus } from "../../lib/focusStatusBus";
import { MORNING_UPDATED_EVENT } from "./ConfirmPlanButton";

function localYmd(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function bibleDoneToday(status: ReturnType<typeof useFocusStatus>): boolean {
  const today = localYmd();
  const goals = status.softland?.goals;
  if (goals?.bible_done) {
    const date = typeof goals.bible_done_for_date === "string" ? goals.bible_done_for_date : "";
    if (date === today) return true;
  }
  const loop = status.dayLoop;
  if (!loop?.bible_done) return false;
  const date = typeof loop.date === "string" ? loop.date : "";
  // Stale day_loop from yesterday must not skip the morning gate.
  return date === today;
}

/**
 * New-day surface: SoftLand morning.next=bible until chapter marked done today.
 * Wake / first open must open Bible and read — no skip mark-done from this overlay.
 */
export default function MorningBibleOverlay() {
  const focus = isFocusDesktopShell();
  const status = useFocusStatus();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!focus) return;
    const kickPipe = () => invalidateFocusStatusBus({ pipe: true });
    kickPipe();
    const onMorning = () => kickPipe();
    window.addEventListener(MORNING_UPDATED_EVENT, onMorning);
    const id = window.setInterval(() => invalidateFocusStatusBus({ pipe: false }), 12_000);
    return () => {
      window.removeEventListener(MORNING_UPDATED_EVENT, onMorning);
      window.clearInterval(id);
    };
  }, [focus]);

  const path = (location.pathname || "").toLowerCase();
  const onBible = path.includes("bible");
  const blocking =
    focus &&
    !status.dayLoop?.bedtime_active &&
    Boolean(status.dayLoop || status.softland?.goals) &&
    !bibleDoneToday(status);

  useEffect(() => {
    if (!blocking) return;
    if (onBible) return;
    navigate("/bible", { replace: true });
  }, [blocking, onBible, navigate]);

  if (!blocking || onBible) return null;

  return (
    <div
      className="fixed inset-0 z-[190] flex items-center justify-center px-6 py-10"
      style={{
        background:
          "radial-gradient(ellipse 90% 70% at 50% 0%, #2a3218 0%, #12160e 55%, #070908 100%)",
      }}
    >
      <div className="flex w-full max-w-md flex-col items-stretch text-left">
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-amber-200/45">
          CALT Focus
        </p>
        <h1 className="mt-3 text-[2rem] font-semibold leading-tight tracking-tight text-amber-50">
          Morning chapter
        </h1>
        <p className="mt-3 text-[15px] leading-relaxed text-amber-100/65">
          Read today&apos;s chapter first. Mark done is only on the Bible page after you open the
          reading — SoftLand and Arm stay gated until then.
        </p>

        <button
          type="button"
          onClick={() => navigate("/bible")}
          className="mt-8 w-full rounded-lg bg-amber-300 px-4 py-3 text-sm font-semibold text-amber-950 transition-colors hover:bg-amber-200"
        >
          Open Bible
        </button>
      </div>
    </div>
  );
}
