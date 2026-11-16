import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Plus, Save, Trash2 } from "lucide-react";
import {
  fetchGateSchedules,
  saveGateSchedules,
  type GateSchedulesResponse,
  type GateScheduleWindow,
} from "../../api/behaviorClient";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { focusDataUrl } from "../../utils/focusDataUrl";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function newWindow(): GateScheduleWindow {
  return {
    id: `win-${Date.now()}`,
    label: "New window",
    days: [0, 1, 2, 3, 4],
    start: "09:00",
    end: "17:00",
    mode: "study",
  };
}

async function loadSchedulesFocus(): Promise<GateSchedulesResponse> {
  const r = await fetch(focusDataUrl("softland_policy.json"), { cache: "no-store" });
  if (!r.ok) throw new Error(`softland_policy.json: ${r.status}`);
  const j = (await r.json()) as {
    schedules?: GateSchedulesResponse;
  };
  if (j.schedules && typeof j.schedules === "object") {
    return {
      enabled: Boolean(j.schedules.enabled),
      windows: Array.isArray(j.schedules.windows) ? j.schedules.windows : [],
    };
  }
  return { enabled: false, windows: [newWindow()] };
}

export function GateSchedulesPanel({ compact = false }: { compact?: boolean }) {
  const [data, setData] = useState<GateSchedulesResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      if (isFocusDesktopShell()) {
        setData(await loadSchedulesFocus());
      } else {
        setData(await fetchGateSchedules());
      }
      setError(null);
    } catch (e: unknown) {
      const raw = e instanceof Error ? e.message : "Failed to load schedules";
      setData({ enabled: false, windows: [newWindow()] });
      setError(
        raw === "Failed to fetch"
          ? "Can't reach Focus data — empty schedule shown until enforcer / shell is up."
          : raw,
      );
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const updateWindow = (idx: number, patch: Partial<GateScheduleWindow>) => {
    if (!data) return;
    const windows = data.windows.map((w, i) => (i === idx ? { ...w, ...patch } : w));
    setData({ ...data, windows });
    setSaved(false);
  };

  const addWindow = () => {
    if (!data) return;
    setData({ ...data, windows: [...data.windows, newWindow()] });
    setSaved(false);
  };

  const deleteWindow = (idx: number) => {
    if (!data) return;
    if (data.windows.length <= 1) {
      setError("Keep at least one window (or disable schedules).");
      return;
    }
    setData({ ...data, windows: data.windows.filter((_, i) => i !== idx) });
    setSaved(false);
    setError(null);
  };

  const save = async () => {
    if (!data) return;
    setSaving(true);
    setError(null);
    try {
      if (isFocusEnforcerBridgeAvailable()) {
        const res = await enforcerNativeCmd("softland.patch_schedules", {
          enabled: data.enabled,
          windows: data.windows,
        });
        if (res?.ok) {
          setSaved(true);
          setTimeout(() => setSaved(false), 2500);
          return;
        }
        throw new Error("Enforcer gateway rejected schedule save");
      }
      if (isFocusDesktopShell()) {
        throw new Error("Schedule saves need calt_focus.exe (enforcer pipe)");
      }
      setData(await saveGateSchedules(data));
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (!data) {
    return <p className="text-xs text-muted-foreground">Loading gate schedules…</p>;
  }

  return (
    <div className="space-y-4 min-w-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        {!compact ? (
          <div className="min-w-0">
            <h3 className="font-semibold text-sm flex items-center gap-2">
              <CalendarClock size={16} className="text-[#7DCFC4]" />
              Recurring gate schedules
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Week strip is Mon–Sun. First match wins. Incubation still forces study.
            </p>
          </div>
        ) : (
          <span className="sr-only">Recurring gate schedules</span>
        )}
        <div className="flex flex-wrap gap-2 ml-auto">
          <button
            type="button"
            onClick={addWindow}
            className="min-h-11 inline-flex items-center gap-1.5 rounded-lg border border-border/50 px-3 text-[13px] hover:bg-white/5"
          >
            <Plus size={12} /> Add window
          </button>
          <button
            type="button"
            onClick={() => void save()}
            disabled={saving}
            className="min-h-11 inline-flex items-center gap-1.5 rounded-lg border border-[#0B6B63] bg-[#0B6B63] px-4 text-[13px] font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            <Save size={12} /> {saving ? "Saving…" : saved ? "Saved" : "Save"}
          </button>
        </div>
      </div>
      <label className="flex items-center gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={data.enabled}
          onChange={(e) => {
            setData({ ...data, enabled: e.target.checked });
            setSaved(false);
          }}
        />
        Enable recurring schedules
      </label>
      {error ? <p className="text-xs text-rose-300">{error}</p> : null}
      <ul className="space-y-3">
        {data.windows.map((win, idx) => (
          <li key={win.id} className="rounded-xl border border-border/40 bg-background/30 p-3 space-y-2 text-xs min-w-0">
            <div className="flex gap-2 items-start min-w-0">
              <input
                value={win.label}
                onChange={(e) => updateWindow(idx, { label: e.target.value })}
                className="min-w-0 flex-1 rounded-lg border border-border/50 bg-background px-2 py-1.5 font-medium"
              />
              <button
                type="button"
                onClick={() => deleteWindow(idx)}
                className="shrink-0 p-1.5 rounded border border-rose-400/30 text-rose-200/90 hover:bg-rose-500/10"
                title="Delete window"
              >
                <Trash2 size={12} />
              </button>
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              <label className="inline-flex items-center gap-1">
                Start
                <input
                  type="time"
                  value={win.start}
                  onChange={(e) => updateWindow(idx, { start: e.target.value })}
                  className="rounded-lg border border-border/50 bg-background px-2 py-1"
                />
              </label>
              <label className="inline-flex items-center gap-1">
                End
                <input
                  type="time"
                  value={win.end}
                  onChange={(e) => updateWindow(idx, { end: e.target.value })}
                  className="rounded-lg border border-border/50 bg-background px-2 py-1"
                />
              </label>
              <select
                value={win.mode}
                onChange={(e) =>
                  updateWindow(idx, { mode: e.target.value as GateScheduleWindow["mode"] })
                }
                className="rounded-lg border border-border/50 bg-background px-2 py-1"
              >
                <option value="study">Study</option>
                <option value="free">Free</option>
                <option value="planning">Planning</option>
                <option value="bible">Bible</option>
              </select>
            </div>
            <div className="flex flex-wrap gap-1">
              {DAY_LABELS.map((label, dayIdx) => {
                const on = win.days.includes(dayIdx);
                return (
                  <button
                    key={label}
                    type="button"
                    onClick={() => {
                      const days = on
                        ? win.days.filter((d) => d !== dayIdx)
                        : [...win.days, dayIdx].sort();
                      updateWindow(idx, { days });
                    }}
                    className={`px-2 py-0.5 rounded border text-[10px] ${
                      on
                        ? "border-[#0B6B63]/50 bg-[#0B6B63]/20 text-[#7DCFC4]"
                        : "border-border/40 text-muted-foreground"
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default GateSchedulesPanel;
