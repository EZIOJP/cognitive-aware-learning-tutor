/**
 * Focus day-loop client — reads from day_loop.json mirror; writes via pipe.
 */
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../lib/enforcerNativeCmd";
import { fetchDayLoopMirror } from "./focusMirrors";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";

export type DayLoopTask = {
  id: number;
  title: string;
  done: boolean;
  sort_order?: number;
  task_date?: string;
};

export type DayLoopSnapshot = {
  date: string;
  planned_minutes: number;
  tracked_productive_minutes: number;
  threshold_minutes: number;
  tasks_total: number;
  tasks_done: number;
  checkboxes_ok: boolean;
  time_ok: boolean;
  dual_gate_ok: boolean;
  closeout_free_granted: boolean;
  free_until: string | null;
  bedtime_hm: string | null;
  wake_hm: string | null;
  bedtime_active: boolean;
  emergency_until: string | null;
  bible_done: boolean;
  plan_confirmed: boolean;
  softland_enabled: boolean;
  tasks: DayLoopTask[];
};

function todayYmd(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export async function confirmPlanNative(): Promise<{ ok: boolean; error?: string }> {
  if (!isFocusEnforcerBridgeAvailable()) return { ok: false, error: "no_bridge" };
  const r = await enforcerNativeCmd("day.confirm_plan", {});
  if (!r?.ok) {
    const err = String(r?.error || "confirm_failed");
    if (err === "bible_required") return { ok: false, error: "Finish Bible reading first" };
    return { ok: false, error: err };
  }
  return { ok: true };
}

export async function fetchDayLoopSnapshot(): Promise<DayLoopSnapshot | null> {
  if (isFocusDesktopShell()) {
    const mir = await fetchDayLoopMirror();
    if (mir && typeof mir === "object" && mir.date) {
      const loop = mir as unknown as DayLoopSnapshot;
      return { ...loop, tasks: Array.isArray(loop.tasks) ? loop.tasks : [] };
    }
  }
  if (!isFocusEnforcerBridgeAvailable()) return null;
  const r = await enforcerNativeCmd("day.loop_snapshot", {});
  if (!r?.ok) return null;
  const loop = r.loop as DayLoopSnapshot | undefined;
  if (!loop || typeof loop !== "object") return null;
  return {
    ...loop,
    tasks: Array.isArray(loop.tasks) ? loop.tasks : [],
  };
}

export async function upsertDayTask(input: {
  id?: number;
  title: string;
  done?: boolean;
  sort_order?: number;
  task_date?: string;
}): Promise<DayLoopTask | null> {
  if (!isFocusEnforcerBridgeAvailable()) return null;
  const r = await enforcerNativeCmd("day.task_upsert", {
    ...input,
    task_date: input.task_date || todayYmd(),
  });
  if (!r?.ok) return null;
  return (r.task as DayLoopTask) || null;
}

export async function setDayTaskDone(id: number, done: boolean): Promise<boolean> {
  if (!isFocusEnforcerBridgeAvailable()) return false;
  const r = await enforcerNativeCmd("day.task_set_done", { id, done });
  return Boolean(r?.ok);
}

export async function deleteDayTask(id: number): Promise<boolean> {
  if (!isFocusEnforcerBridgeAvailable()) return false;
  const r = await enforcerNativeCmd("day.task_delete", { id });
  return Boolean(r?.ok);
}

export async function evaluateDayClose(): Promise<{
  ok: boolean;
  granted?: boolean;
  free_until?: string;
  loop?: DayLoopSnapshot;
  error?: string;
}> {
  if (!isFocusEnforcerBridgeAvailable()) return { ok: false, error: "no_bridge" };
  const r = await enforcerNativeCmd("day.evaluate_close", {});
  if (!r?.ok) return { ok: false, error: String(r?.error || "evaluate_failed") };
  return {
    ok: true,
    granted: Boolean(r.granted),
    free_until: typeof r.free_until === "string" ? r.free_until : undefined,
    loop: r.loop as DayLoopSnapshot | undefined,
  };
}

export async function setBedtime(bedtime_hm: string, wake_hm?: string): Promise<boolean> {
  if (!isFocusEnforcerBridgeAvailable()) return false;
  const payload: Record<string, string> = { bedtime_hm };
  if (wake_hm) payload.wake_hm = wake_hm;
  const r = await enforcerNativeCmd("softland.set_bedtime", payload);
  return Boolean(r?.ok);
}

export async function emergencyWinddown(minutes = 30): Promise<{ ok: boolean; error?: string }> {
  if (!isFocusEnforcerBridgeAvailable()) return { ok: false, error: "no_bridge" };
  const r = await enforcerNativeCmd("softland.emergency_winddown", {
    confirm: "EMERGENCY",
    minutes,
  });
  if (!r?.ok) return { ok: false, error: String(r?.error || "failed") };
  return { ok: true };
}

export async function importBlocksFromDate(from_date: string): Promise<number> {
  if (!isFocusEnforcerBridgeAvailable()) return 0;
  const r = await enforcerNativeCmd("plan.import_from_date", { from_date });
  if (!r?.ok) return 0;
  return typeof r.imported === "number" ? r.imported : 0;
}

export { todayYmd };
