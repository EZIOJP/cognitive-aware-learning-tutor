import { useMemo, useState } from "react";
import { Loader2, ShieldCheck } from "lucide-react";
import { patchTrackedSession, type DesktopTimeline } from "../../api/behaviorClient";
import { fmtDurationMinutes, scoreLabel, shortAppName } from "./planVsActualUtils";

type Props = {
  timeline: DesktopTimeline | null;
  onSaved?: () => void;
};

export function SessionOverridePanel({ timeline, onSaved }: Props) {
  const sessions = useMemo(
    () => [...(timeline?.intervals ?? [])].sort((a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime()).slice(0, 25),
    [timeline],
  );
  const [selectedId, setSelectedId] = useState(sessions[0]?.session_id ?? "");
  const [saving, setSaving] = useState(false);
  const [hint, setHint] = useState<string | null>(null);

  const selected = sessions.find((s) => s.session_id === selectedId) ?? sessions[0] ?? null;

  const apply = async (override: boolean | null) => {
    if (!selected) return;
    setSaving(true);
    setHint(null);
    try {
      await patchTrackedSession(selected.session_id, { override_productive: override });
      setHint(
        override === true
          ? "Marked productive for this session."
          : override === false
            ? "Marked unproductive for this session."
            : "Cleared override for this session.",
      );
      onSaved?.();
    } catch (e: unknown) {
      setHint(e instanceof Error ? e.message : "Override failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="gloss-panel rounded-xl p-4 space-y-3">
      <div>
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <ShieldCheck size={14} className="text-sky-300" />
          Session productivity review
        </h3>
        <p className="text-xs text-muted-foreground mt-1">
          One-off corrections live here so activity details stay uncluttered.
        </p>
      </div>

      {sessions.length === 0 ? (
        <p className="text-sm text-muted-foreground py-4">No tracked sessions for the selected day yet.</p>
      ) : (
        <>
          <select
            value={selected?.session_id ?? ""}
            onChange={(e) => setSelectedId(e.target.value)}
            className="w-full rounded border border-white/10 bg-black/30 px-2 py-1.5 text-xs"
          >
            {sessions.map((s) => (
              <option key={s.session_id} value={s.session_id}>
                {new Date(s.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} ·{" "}
                {s.site || shortAppName(s.app_name || s.category)} · {fmtDurationMinutes(Math.round(s.duration_seconds / 60))} ·{" "}
                {s.productivity_score ?? 35} {scoreLabel(s.productivity_score)}
              </option>
            ))}
          </select>

          {selected && (
            <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-xs space-y-1">
              <div className="flex justify-between gap-2">
                <span className="font-medium text-sky-100">
                  {selected.site || shortAppName(selected.app_name || selected.category)}
                </span>
                <span className="text-muted-foreground tabular-nums">
                  {new Date(selected.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} –{" "}
                  {new Date(selected.end_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </span>
              </div>
              <p className="text-muted-foreground">
                {selected.category} · {selected.productivity_score ?? 35} {scoreLabel(selected.productivity_score)}
                {selected.source ? ` · ${selected.source}` : ""}
              </p>
              {selected.window_title && (
                <p className="text-sky-200/70 line-clamp-2" title={selected.window_title}>{selected.window_title}</p>
              )}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={saving}
              onClick={() => void apply(true)}
              className="px-3 py-1.5 rounded border border-emerald-500/30 text-emerald-200 hover:bg-emerald-500/10 disabled:opacity-50 text-xs"
            >
              {saving ? <Loader2 size={12} className="animate-spin" /> : "Mark productive"}
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={() => void apply(false)}
              className="px-3 py-1.5 rounded border border-rose-500/30 text-rose-200 hover:bg-rose-500/10 disabled:opacity-50 text-xs"
            >
              Mark unproductive
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={() => void apply(null)}
              className="px-3 py-1.5 rounded border border-white/15 text-sky-200/80 hover:bg-white/5 disabled:opacity-50 text-xs"
            >
              Clear override
            </button>
          </div>
        </>
      )}

      {hint && <p className="text-xs text-sky-300">{hint}</p>}
    </div>
  );
}

export default SessionOverridePanel;
