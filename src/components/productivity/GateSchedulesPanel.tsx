import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Save } from "lucide-react";
import {
  fetchGateSchedules,
  saveGateSchedules,
  type GateSchedulesResponse,
  type GateScheduleWindow,
} from "../../api/behaviorClient";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function GateSchedulesPanel() {
  const [data, setData] = useState<GateSchedulesResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await fetchGateSchedules());
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load schedules");
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

  const save = async () => {
    if (!data) return;
    setSaving(true);
    setError(null);
    try {
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
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-sm flex items-center gap-2">
            <CalendarClock size={16} className="text-primary" />
            Recurring gate schedules
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Freedom-style windows — force study or free browser mode by time of day.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/70 hover:bg-emerald-600 text-xs disabled:opacity-50"
        >
          <Save size={12} /> {saving ? "Saving…" : saved ? "Saved" : "Save"}
        </button>
      </div>
      <label className="flex items-center gap-2 text-xs">
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
          <li key={win.id} className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2 text-xs">
            <input
              value={win.label}
              onChange={(e) => updateWindow(idx, { label: e.target.value })}
              className="w-full rounded border border-white/10 bg-black/30 px-2 py-1 font-medium"
            />
            <div className="flex flex-wrap gap-2 items-center">
              <label>
                Start
                <input
                  type="time"
                  value={win.start}
                  onChange={(e) => updateWindow(idx, { start: e.target.value })}
                  className="ml-1 rounded border border-white/10 bg-black/30 px-2 py-1"
                />
              </label>
              <label>
                End
                <input
                  type="time"
                  value={win.end}
                  onChange={(e) => updateWindow(idx, { end: e.target.value })}
                  className="ml-1 rounded border border-white/10 bg-black/30 px-2 py-1"
                />
              </label>
              <select
                value={win.mode}
                onChange={(e) =>
                  updateWindow(idx, { mode: e.target.value as GateScheduleWindow["mode"] })
                }
                className="rounded border border-white/10 bg-black/30 px-2 py-1"
              >
                <option value="study">Study</option>
                <option value="free">Free</option>
                <option value="planning">Planning</option>
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
                        ? "border-indigo-400/50 bg-indigo-500/20 text-indigo-100"
                        : "border-white/10 text-muted-foreground"
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
