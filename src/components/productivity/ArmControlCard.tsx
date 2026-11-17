/**
 * Slim Arm controls for Settings → Unlock.
 * SoftLand ≠ Arm. Kill membership is edited on Blocks → Board.
 * Lock mode / anti-tamper UI removed — free-day gate protects Arm edits.
 */
import { useCallback, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import {
  fetchFocusDashboard,
  putEnforcerPolicy,
  type FocusDashboardSnapshot,
} from "../../api/behaviorClient";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { invalidateFocusStatusBus } from "../../lib/focusStatusBus";
import { useFocusStatus, useFreeDay } from "../../hooks/useFocusStatus";
import { focusDataUrl } from "../../utils/focusDataUrl";
import { cn } from "../../app/components/ui/utils";

export function ArmControlCard() {
  const status = useFocusStatus();
  const freeDay = useFreeDay();
  const [snap, setSnap] = useState<FocusDashboardSnapshot | null>(null);
  const [exes, setExes] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await fetchFocusDashboard();
      setSnap(s);
      setError(null);
      const list = s.enforcer_policy?.exes;
      if (Array.isArray(list)) setExes(list.map(String));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      try {
        const r = await fetch(focusDataUrl("enforcer_policy.json"), { cache: "no-store" });
        if (r.ok) {
          const pol = (await r.json()) as { exes?: string[] };
          if (Array.isArray(pol.exes)) setExes(pol.exes.map(String));
        }
      } catch {
        /* keep last */
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    if (!hint) return;
    const t = window.setTimeout(() => setHint(null), 5000);
    return () => window.clearTimeout(t);
  }, [hint]);

  const pol = snap?.enforcer_policy;
  const armedShown = Boolean(
    snap?.active?.hard_block_armed ||
      pol?.hard_block_armed ||
      snap?.enforcer?.armed ||
      status.enforcerStatus?.armed,
  );
  const killCount = exes.length;

  async function setArmed(armed: boolean) {
    if (!freeDay) {
      setHint(
        "Arm changes after Confirm need a free day or day pass. Finish Plan → Confirm first, or claim Unlock free time.",
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const killList = exes.map((s) => s.trim()).filter(Boolean);
      if (armed) {
        const body: Parameters<typeof putEnforcerPolicy>[0] = {
          hard_block_armed: true,
          gate_locked: true,
          incubation_active: false,
          exes: killList,
          lock_mode: "none",
          anti_tamper: false,
        };

        if (isFocusEnforcerBridgeAvailable()) {
          const native = await enforcerNativeCmd("arm.set", {
            hard_block_armed: true,
            gate_locked: true,
            incubation_active: false,
            exes: killList,
            lock_mode: "none",
            anti_tamper: false,
          });
          if (native?.ok) {
            setHint(
              killList.length
                ? `Armed — killing ${killList.length} listed app(s).`
                : "Armed — kill list is empty; add apps below.",
            );
            window.setTimeout(() => {
              invalidateFocusStatusBus({ pipe: true });
              void refresh();
            }, 400);
            return;
          }
        }

        await putEnforcerPolicy(body);
        setHint("Armed via policy write.");
      } else {
        let provided = "";
        const mode = String(pol?.lock_mode || "none");
        if (mode === "password" || mode === "phrase") {
          provided = window.prompt(mode === "password" ? "Unlock password" : "Unlock phrase") ?? "";
        }

        if (isFocusEnforcerBridgeAvailable()) {
          const native = await enforcerNativeCmd("arm.set", {
            hard_block_armed: false,
            gate_locked: false,
            incubation_active: false,
            exes: killList,
            lock_mode: "none",
            provided_unlock: provided,
            anti_tamper: false,
          });
          if (native?.ok) {
            setHint("Disarmed.");
            window.setTimeout(() => {
              invalidateFocusStatusBus({ pipe: true });
              void refresh();
            }, 400);
            return;
          }
          if (native?.error === "unlock_failed") {
            throw new Error("Unlock password/phrase did not match.");
          }
        }

        await putEnforcerPolicy({
          hard_block_armed: false,
          gate_locked: false,
          incubation_active: false,
          exes: killList,
          lock_mode: "none",
          provided_unlock: provided,
          anti_tamper: false,
        });
        setHint("Disarmed.");
      }
      window.setTimeout(() => {
        invalidateFocusStatusBus({ pipe: true });
        void refresh();
      }, 400);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-[13px] leading-relaxed text-muted-foreground">
        Arm on kills apps on the Blocks board kill list about every 1.5s. SoftLand free does not
        disarm Arm. Bedtime keeps kills on even after a goal unlock.
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "rounded-full border px-2.5 py-0.5 text-xs font-medium",
            armedShown
              ? "border-rose-500/50 bg-rose-500/15 text-rose-100"
              : "border-border text-muted-foreground",
          )}
        >
          {armedShown ? "Armed" : "Disarmed"}
        </span>
        <span className="rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
          {killCount} on kill list
        </span>
        {!freeDay ? (
          <span className="rounded-full border border-amber-400/35 bg-amber-500/10 px-2.5 py-0.5 text-xs text-amber-100">
            Free day / pass needed to change Arm
          </span>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || !freeDay}
          onClick={() => void setArmed(true)}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-600/20 px-3 text-sm text-rose-100 disabled:opacity-40"
        >
          {busy ? <Loader2 size={13} className="animate-spin" /> : null}
          Arm hard block
        </button>
        <button
          type="button"
          disabled={busy || !freeDay}
          onClick={() => void setArmed(false)}
          className="inline-flex min-h-10 items-center rounded-lg border border-border px-3 text-sm hover:bg-muted/40 disabled:opacity-40"
        >
          Disarm
        </button>
      </div>

      {hint ? <p className="text-[12px] text-teal-200/90">{hint}</p> : null}
      {error ? <p className="text-[12px] text-rose-300">{error}</p> : null}

      <details className="rounded-lg border border-border/40 bg-background/20 open:pb-1">
        <summary className="cursor-pointer list-none px-3 py-2 text-[12px] text-muted-foreground marker:content-none [&::-webkit-details-marker]:hidden">
          Kill list preview · edit on Blocks → Board
        </summary>
        <div className="flex flex-wrap gap-1.5 border-t border-border/30 px-3 py-2">
          {exes.length === 0 ? (
            <span className="text-[11px] text-muted-foreground">Empty — add apps in Kill list.</span>
          ) : (
            exes.slice(0, 24).map((exe) => (
              <span
                key={exe}
                className="rounded-md border border-rose-400/30 bg-rose-500/10 px-2 py-0.5 text-[11px] font-mono text-rose-100"
              >
                {exe}
              </span>
            ))
          )}
          {exes.length > 24 ? (
            <span className="text-[11px] text-muted-foreground">+{exes.length - 24} more</span>
          ) : null}
        </div>
      </details>
    </div>
  );
}

export default ArmControlCard;
