/** HTML5 drag payload: Daily routines → PlanningDayAgenda hour slots */

export const ROUTINE_DRAG_MIME = "application/x-calt-routine";

export type RoutineDragPayload = {
  title: string;
  category: string;
  duration_minutes: number;
  color?: string | null;
};

/** True while a routine row drag is in progress (MIME types are unreliable mid-drag). */
let routineDragActive = false;

export function isRoutineDragActive(): boolean {
  return routineDragActive;
}

export function setRoutineDragData(dt: DataTransfer, payload: RoutineDragPayload): void {
  const json = JSON.stringify(payload);
  dt.setData(ROUTINE_DRAG_MIME, json);
  dt.setData("text/plain", json);
  dt.effectAllowed = "copy";
  routineDragActive = true;
}

export function clearRoutineDragActive(): void {
  routineDragActive = false;
}

export function readRoutineDragData(dt: DataTransfer): RoutineDragPayload | null {
  const raw = dt.getData(ROUTINE_DRAG_MIME) || dt.getData("text/plain");
  if (!raw) return null;
  try {
    const o = JSON.parse(raw) as RoutineDragPayload;
    if (!o || typeof o.title !== "string" || !o.title.trim()) return null;
    const mins = Number(o.duration_minutes);
    return {
      title: o.title.trim(),
      category: String(o.category || "personal"),
      duration_minutes: Number.isFinite(mins) && mins > 0 ? Math.min(240, Math.round(mins)) : 30,
      color: o.color ?? null,
    };
  } catch {
    return null;
  }
}

export function hasRoutineDrag(dt: DataTransfer): boolean {
  if (routineDragActive) return true;
  const types = Array.from(dt.types || []);
  return types.includes(ROUTINE_DRAG_MIME);
}
