/**
 * Optional SoftLand free + Arm pause for a timed window (not the low-CPU sleeper).
 * For gaming CPU: use Game Sleeper (FocusSleeperPanel) — unloads models without SoftLand free.
 * SoftLand ≠ Arm under the hood.
 */
import { useCallback, useEffect, useState } from "react";
import { Gamepad2, Loader2, Square } from "lucide-react";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { invalidateFocusStatusBus } from "../../lib/focusStatusBus";
import { useFocusStatus, useFreeDay } from "../../hooks/useFocusStatus";
import { focusDataUrl } from "../../utils/focusDataUrl";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { cn } from "../../app/components/ui/utils";

type GameMirror = {
  active?: boolean;
  until?: string | null;
  started_at?: string | null;
};

const PRESETS = [30, 60, 90, 120] as const;

function remainingLabel(until: string | null | undefined): string {
  if (!until) return "";
  const end = Date.parse(until.length === 19 ? until.replace(" ", "T") : until);
  if (!Number.isFinite(end)) return until.slice(11, 16);
  const ms = end - Date.now();
  if (ms <= 0) return "ending…";
  const m = Math.ceil(ms / 60000);
  if (m >= 60) return `${Math.floor(m / 60)}h ${m % 60}m left`;
  return `${m}m left`;
}

export function GameSessionPanel() {
  const status = useFocusStatus();
  const freeDay = useFreeDay();
  const [mirror, setMirror] = useState<GameMirror | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [, setTick] = useState(0);

  const loop = status.dayLoop as {
    game_session_active?: boolean;
    game_session_until?: string | null;
    free_until?: string | null;
  } | null;

  const active = Boolean(mirror?.active || loop?.game_session_active);
  const until = mirror?.until || loop?.game_session_until || null;
  const freeOpen = freeDay || Boolean(loop?.free_until);
  const bedtime = Boolean(
    (status.dayLoop as { bedtime_active?: boolean } | null)?.bedtime_active,
  );

  const load = useCallback(async () => {
    try {
      if (isFocusDesktopShell()) {
        const r = await fetch(focusDataUrl("game_session.json"), { cache: "no-store" });
        if (r.ok) setMirror((await r.json()) as GameMirror);
        else setMirror({ active: false });
      }
    } catch {
      /* keep */
    }
  }, []);

  useEffect(() => {
    void load();
    const t = window.setInterval(() => {
      void load();
      setTick((n) => n + 1);
    }, 15_000);
    return () => window.clearInterval(t);
  }, [load]);

  useEffect(() => {
    if (!hint) return;
    const t = window.setTimeout(() => setHint(null), 5000);
    return () => window.clearTimeout(t);
  }, [hint]);

  const start = async (minutes: number) => {
    if (!isFocusEnforcerBridgeAvailable()) {
      setError("Open CALT Focus (WebView) — design host cannot start a Game Session.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await enforcerNativeCmd("game.session.start", { minutes }, 15000);
      if (!res || res.ok === false) {
        const err = String(res?.error || "start_failed");
        if (err === "need_free_time") {
          setError("Unlock free time first (goal / reward / day pass), then start a Game Session.");
        } else if (err === "bedtime_active") {
          setError("Bedtime is on — Game Session is blocked until wake.");
        } else {
          setError(err);
        }
        return;
      }
      setHint(`Game Session ${minutes}m — SoftLand free, Arm paused, tracking asleep.`);
      invalidateFocusStatusBus({ pipe: true });
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    if (!isFocusEnforcerBridgeAvailable()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await enforcerNativeCmd("game.session.stop", {}, 12000);
      if (!res || res.ok === false) {
        setError(String(res?.error || "stop_failed"));
        return;
      }
      setHint("Game Session ended — tracking and Arm follow normal free/rules again.");
      invalidateFocusStatusBus({ pipe: true });
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-[15px] font-semibold flex items-center gap-2">
            <Gamepad2 size={16} className="text-[#7DCFC4]" />
            SoftLand game free
          </h3>
          <p className="text-[13px] text-muted-foreground mt-1 max-w-xl leading-relaxed">
            Optional: SoftLand free + Arm pause + FG tracking sleep for a timed window. Not the
            low-CPU Game Sleeper above — use that to drop models/CPU without changing SoftLand.
            SoftLand ≠ Arm. Needs Unlock free first.
          </p>
        </div>
        {active ? (
          <span className="rounded-full border border-emerald-400/35 bg-emerald-500/15 px-2.5 py-1 text-[12px] font-medium text-emerald-100">
            Live · {remainingLabel(until)}
          </span>
        ) : null}
      </div>

      {active ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => void stop()}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-rose-400/40 bg-rose-500/15 px-3 text-sm font-medium text-rose-100 hover:bg-rose-500/25 disabled:opacity-40"
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Square size={14} />}
          End Game Session
        </button>
      ) : (
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((m) => (
            <button
              key={m}
              type="button"
              disabled={busy || bedtime || !freeOpen}
              onClick={() => void start(m)}
              className={cn(
                "inline-flex min-h-10 items-center rounded-lg border border-border/50 bg-background/40 px-3 text-sm hover:bg-accent/40 disabled:opacity-40",
              )}
              title={
                bedtime
                  ? "Blocked during bedtime"
                  : !freeOpen
                    ? "Need goal/reward/pass free first"
                    : `Start ${m} minute game session`
              }
            >
              {busy ? <Loader2 size={14} className="animate-spin mr-1" /> : null}
              {m}m
            </button>
          ))}
        </div>
      )}

      {!freeOpen && !active ? (
        <p className="text-[12px] text-amber-100/90">
          Hit the daily goal or use a reward / day pass under Unlock, then start a session.
        </p>
      ) : null}
      {error ? <p className="text-[12px] text-rose-300">{error}</p> : null}
      {hint ? <p className="text-[12px] text-emerald-200/90">{hint}</p> : null}
    </div>
  );
}

export default GameSessionPanel;
