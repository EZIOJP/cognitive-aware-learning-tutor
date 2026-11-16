/**
 * Slim Arm controls for Blocks → Apps.
 * SoftLand ≠ Arm. Kill list CRUD stays in AppKillRulesPanel below.
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

type LockMode = "none" | "timer" | "password" | "phrase";

export function ArmControlCard() {
  const status = useFocusStatus();
  const freeDay = useFreeDay();
  const [snap, setSnap] = useState<FocusDashboardSnapshot | null>(null);
  const [exes, setExes] = useState<string[]>([]);
  const [lockMode, setLockMode] = useState<LockMode>("none");
  const [timerMinutes, setTimerMinutes] = useState(25);
  const [lockSecret, setLockSecret] = useState("");
  const [antiTamper, setAntiTamper] = useState(true);
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
      const lm = String(s.enforcer_policy?.lock_mode || "none");
      if (lm === "timer" || lm === "password" || lm === "phrase" || lm === "none") {
        setLockMode(lm);
      }
      if (typeof s.enforcer_policy?.anti_tamper === "boolean") {
        setAntiTamper(s.enforcer_policy.anti_tamper);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      try {
        const r = await fetch(focusDataUrl("enforcer_policy.json"), { cache: "no-store" });
        if (r.ok) {
          const pol = (await r.json()) as {
            exes?: string[];
            lock_mode?: string;
            anti_tamper?: boolean;
          };
          if (Array.isArray(pol.exes)) setExes(pol.exes.map(String));
          const lm = String(pol.lock_mode || "none");
          if (lm === "timer" || lm === "password" || lm === "phrase" || lm === "none") {
            setLockMode(lm);
          }
          if (typeof pol.anti_tamper === "boolean") setAntiTamper(pol.anti_tamper);
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
          lock_mode: lockMode,
          anti_tamper: antiTamper,
        };
        if (lockMode === "timer") {
          body.lock_until_unix = Math.floor(Date.now() / 1000) + Math.max(1, timerMinutes) * 60;
        }
        if (lockMode === "password") body.unlock_password = lockSecret;
        if (lockMode === "phrase") body.unlock_phrase = lockSecret;

        if (isFocusEnforcerBridgeAvailable()) {
          const native = await enforcerNativeCmd("arm.set", {
            hard_block_armed: true,
            gate_locked: true,
            incubation_active: false,
            exes: killList,
            lock_mode: lockMode,
            anti_tamper: antiTamper,
            lock_until_unix: body.lock_until_unix,
            unlock_password: body.unlock_password,
            unlock_phrase: body.unlock_phrase,
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
        const mode = String(pol?.lock_mode || lockMode || "none");
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
            anti_tamper: antiTamper,
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
          provided_unlock: provided,
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
        Arm on kills processes on the kill list about every 1.5s. SoftLand (browser) is a separate
        switch under Blocks → Sites. Free SoftLand does not disarm Arm.
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

      <label className="block text-xs text-muted-foreground space-y-1 max-w-md">
        <span>Lock mode (required to disarm when set)</span>
        <select
          value={lockMode}
          onChange={(e) => setLockMode(e.target.value as LockMode)}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
        >
          <option value="none">None</option>
          <option value="timer">Timer</option>
          <option value="password">Password</option>
          <option value="phrase">Phrase</option>
        </select>
      </label>

      {lockMode === "timer" ? (
        <label className="block text-xs text-muted-foreground space-y-1 max-w-md">
          <span>Lock minutes</span>
          <input
            type="number"
            min={1}
            max={24 * 60}
            value={timerMinutes}
            onChange={(e) => setTimerMinutes(Math.max(1, parseInt(e.target.value, 10) || 1))}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
        </label>
      ) : null}

      {lockMode === "password" || lockMode === "phrase" ? (
        <label className="block text-xs text-muted-foreground space-y-1 max-w-md">
          <span>{lockMode === "password" ? "Unlock password" : "Unlock phrase"}</span>
          <input
            type={lockMode === "password" ? "password" : "text"}
            value={lockSecret}
            onChange={(e) => setLockSecret(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
        </label>
      ) : null}

      <label className="flex items-center gap-2 text-xs text-muted-foreground">
        <input
          type="checkbox"
          checked={antiTamper}
          onChange={(e) => setAntiTamper(e.target.checked)}
        />
        Anti-tamper while locked
      </label>

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
          Kill list preview · edit below
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
