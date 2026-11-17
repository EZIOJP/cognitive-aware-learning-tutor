import { useCallback, useEffect, useRef, useState } from "react";
import { Plus, Save, Timer } from "lucide-react";
import { useFreeDay } from "../../hooks/useFocusStatus";
import { focusDataUrl } from "../../utils/focusDataUrl";

type LimitRow = { exe: string; daily_minutes: number };
type UsageRow = {
  exe: string;
  used_seconds: number;
  limit_seconds: number;
  remaining_seconds: number;
  blocked?: boolean;
  over_limit?: boolean;
};
type LimitsDoc = {
  enabled?: boolean;
  date?: string;
  limits?: LimitRow[];
  usage?: UsageRow[];
};

const QUICK: { exe: string; minutes: number; label: string }[] = [
  { exe: "steam.exe", minutes: 60, label: "Steam · 1h" },
  { exe: "discord.exe", minutes: 45, label: "Discord · 45m" },
  { exe: "robloxplayerbeta.exe", minutes: 45, label: "Roblox · 45m" },
  { exe: "spotify.exe", minutes: 90, label: "Spotify · 1.5h" },
];

const BROWSERS = new Set([
  "chrome.exe",
  "msedge.exe",
  "firefox.exe",
  "brave.exe",
  "opera.exe",
  "vivaldi.exe",
  "iexplore.exe",
]);

function normalizeExe(raw: string): string {
  let s = raw.trim().toLowerCase();
  if (!s || s.includes("\\") || s.includes("/") || s.includes(":")) return "";
  if (!s.endsWith(".exe")) s = `${s}.exe`;
  if (!/^[a-z0-9][a-z0-9._-]{0,59}\.exe$/.test(s)) return "";
  return s;
}

function localToday(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function fmt(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return m > 0 ? `${h}h ${m}m` : `${h}h`;
  if (m > 0) return r > 0 ? `${m}m ${r}s` : `${m}m`;
  return `${r}s`;
}

function explain(err: string): string {
  switch (err) {
    case "protected_exe":
      return "Windows and CALT itself can't take a time limit.";
    case "browser_exe":
      return "Browsers are limited under Blocks → Sites.";
    case "bad_exe":
      return "Use an app name like steam.exe.";
    case "bad_minutes":
      return "Minutes need to be between 1 and 1440.";
    case "too_many":
      return "32 apps is the maximum.";
    case "limits_write_failed":
      return "Couldn't save. Check that the enforcer is running.";
    case "timeout":
      return "The enforcer didn't answer. Try again.";
    case "enforcer_unreachable":
      return "Save from the CALT Focus app so the enforcer can store the list.";
    case "unknown_op":
      return "The running enforcer doesn't know this command yet. Restart it after the new build.";
    case "free_day_required":
      return "Time limits change on a free day or a day pass.";
    default:
      return err || "Save failed";
  }
}

export function AppTimeLimitsPanel() {
  const freeDay = useFreeDay();
  const [enabled, setEnabled] = useState(false);
  const [rows, setRows] = useState<LimitRow[]>([]);
  const [usage, setUsage] = useState<UsageRow[]>([]);
  const [draftExe, setDraftExe] = useState("");
  const [draftMin, setDraftMin] = useState(60);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const dirtyRef = useRef(false);
  const loadedRef = useRef(false);

  const applyDoc = useCallback((doc: LimitsDoc, replaceDraft: boolean) => {
    const fresh = !doc.date || doc.date === localToday();
    setUsage(fresh && Array.isArray(doc.usage) ? doc.usage : []);
    if (!replaceDraft) return;
    setEnabled(Boolean(doc.enabled));
    setRows(
      Array.isArray(doc.limits)
        ? doc.limits
            .map((r) => ({
              exe: normalizeExe(String(r.exe || "")),
              daily_minutes: Math.max(1, Math.min(1440, Number(r.daily_minutes) || 60)),
            }))
            .filter((r) => r.exe)
        : [],
    );
  }, []);

  const load = useCallback(async () => {
    const empty = (): void => {
      if (!dirtyRef.current) applyDoc({ enabled: false, limits: [], usage: [] }, true);
      loadedRef.current = true;
      setLoaded(true);
    };
    try {
      const res = await fetch(focusDataUrl("app_limits.json"), { cache: "no-store" });
      // WebView2 virtual host often throws / non-404 when the mirror file is missing.
      if (res.status === 404) {
        empty();
        setError(null);
        return;
      }
      if (!res.ok) throw new Error(`app_limits: ${res.status}`);
      const doc = (await res.json()) as LimitsDoc;
      applyDoc(doc, !dirtyRef.current);
      setError(null);
      loadedRef.current = true;
      setLoaded(true);
    } catch (e: unknown) {
      const raw = e instanceof Error ? e.message : "Couldn't load time limits";
      // Missing mirror / shell data plane — treat as empty so the panel stays usable.
      if (raw === "Failed to fetch" || raw.includes("NetworkError") || raw.includes("Load failed")) {
        empty();
        setError(null);
        return;
      }
      if (!loadedRef.current) {
        empty();
        setError(
          raw.startsWith("app_limits:")
            ? "Time limits mirror unavailable — add apps and Save when the enforcer is up."
            : raw,
        );
      }
    }
  }, [applyDoc]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 10000);
    return () => window.clearInterval(id);
  }, [load]);

  const mark = () => {
    dirtyRef.current = true;
    setSaved(false);
  };

  const addExe = (raw: string, minutes: number) => {
    if (!freeDay) return;
    const name = normalizeExe(raw);
    if (!name) {
      setError("Use an app name like steam.exe.");
      return;
    }
    if (BROWSERS.has(name)) {
      setError("Browsers are limited under Blocks → Sites.");
      return;
    }
    const mins = Math.max(1, Math.min(1440, Math.round(minutes) || 60));
    setRows((cur) => {
      const next = cur.filter((r) => r.exe !== name);
      next.push({ exe: name, daily_minutes: mins });
      return next;
    });
    setError(null);
    mark();
  };

  const save = async () => {
    if (!freeDay) return;
    setSaving(true);
    setError(null);
    try {
      const { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } = await import(
        "../../lib/enforcerNativeCmd"
      );
      if (!isFocusEnforcerBridgeAvailable()) throw new Error("enforcer_unreachable");
      const limits = rows.map((r) => ({
        exe: r.exe,
        daily_minutes: Math.max(1, Math.min(1440, Math.round(r.daily_minutes) || 60)),
      }));
      const native = await enforcerNativeCmd("app_limits.set", { enabled, limits });
      if (!native || native.ok === false) throw new Error(String(native?.error || "enforcer_cmd_failed"));
      const echoed = native.app_limits as LimitsDoc | undefined;
      dirtyRef.current = false;
      if (echoed && typeof echoed === "object") applyDoc(echoed, true);
      else await load();
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2500);
    } catch (e: unknown) {
      setError(explain(e instanceof Error ? e.message : "Save failed"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs text-muted-foreground max-w-xl flex gap-2">
            <Timer size={16} className="text-amber-300 shrink-0 mt-0.5" />
            <span>
              Each app stays open until its minutes for today are used. CALT then closes it until
              midnight. The kill list below is Arm, a separate switch.
            </span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={!freeDay}
            onClick={() => {
              setEnabled((v) => !v);
              mark();
            }}
            className={`px-2.5 py-1 rounded-lg text-[11px] border ${
              enabled
                ? "border-amber-400/50 bg-amber-500/15 text-amber-100"
                : "border-white/15 text-muted-foreground"
            }`}
            aria-pressed={enabled}
          >
            {enabled ? "On" : "Off"}
          </button>
          <button
            type="button"
            onClick={() => void save()}
            disabled={saving || !freeDay}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/70 hover:bg-emerald-600 text-xs disabled:opacity-50"
          >
            <Save size={12} /> {saving ? "Saving…" : saved ? "Saved" : "Save"}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {QUICK.map((q) => (
          <button
            key={q.exe}
            type="button"
            disabled={!freeDay}
            onClick={() => addExe(q.exe, q.minutes)}
            className="px-2.5 py-1 rounded-lg border border-white/15 text-[11px] hover:bg-white/5"
          >
            {q.label}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        {rows.length === 0 ? (
          <p className="text-[11px] text-muted-foreground">
            {loaded ? "No time limits yet. Add a game or app and how long it may stay open today." : "Loading…"}
          </p>
        ) : (
          rows.map((row) => {
            const u = usage.find((x) => x.exe === row.exe);
            const limitSec = (u?.limit_seconds ?? row.daily_minutes * 60) || 1;
            const used = u?.used_seconds ?? 0;
            const pct = Math.max(0, Math.min(100, (used / limitSec) * 100));
            const blocked = Boolean(enabled && u?.blocked);
            return (
              <div key={row.exe} className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-medium min-w-[8rem]">{row.exe}</span>
                  <label className="flex items-center gap-1 text-[11px] text-muted-foreground">
                    <input
                      type="number"
                      min={1}
                      max={1440}
                      value={row.daily_minutes}
                      disabled={!freeDay}
                      onChange={(e) => {
                        const n = Number(e.target.value);
                        setRows((cur) =>
                          cur.map((r) =>
                            r.exe === row.exe
                              ? { ...r, daily_minutes: Number.isFinite(n) ? n : r.daily_minutes }
                              : r,
                          ),
                        );
                        mark();
                      }}
                      className="w-16 rounded border border-white/10 bg-black/30 px-1.5 py-1 text-xs text-foreground"
                    />
                    min / day
                  </label>
                  <span className="text-[11px] text-muted-foreground ml-auto">
                    {u ? `${fmt(used)} used · ${fmt(u.remaining_seconds ?? 0)} left` : "Starts after save"}
                  </span>
                  <button
                    type="button"
                    disabled={!freeDay}
                    onClick={() => {
                      setRows((cur) => cur.filter((r) => r.exe !== row.exe));
                      mark();
                    }}
                    className="text-[11px] text-rose-300/90 hover:text-rose-200"
                    title="Remove"
                  >
                    Remove
                  </button>
                </div>
                <div className="mt-2 h-1.5 rounded-full bg-white/10 overflow-hidden">
                  <div
                    className={`h-full ${blocked ? "bg-rose-400" : "bg-amber-300/90"}`}
                    style={{ width: `${u ? pct : 0}%` }}
                  />
                </div>
                {blocked ? (
                  <p className="mt-1 text-[11px] text-rose-300">Time's up — closed until midnight.</p>
                ) : null}
              </div>
            );
          })
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <input
          value={draftExe}
          onChange={(e) => setDraftExe(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addExe(draftExe, draftMin);
              setDraftExe("");
            }
          }}
          placeholder="e.g. valorant.exe"
          className="flex-1 min-w-[10rem] rounded border border-white/10 bg-black/30 px-2 py-1.5 text-xs"
        />
        <input
          type="number"
          min={1}
          max={1440}
          value={draftMin}
          onChange={(e) => setDraftMin(Number(e.target.value) || 60)}
          className="w-16 rounded border border-white/10 bg-black/30 px-2 py-1.5 text-xs"
          aria-label="Minutes per day"
        />
        <button
          type="button"
          disabled={!freeDay || !draftExe.trim()}
          onClick={() => {
            addExe(draftExe, draftMin);
            setDraftExe("");
          }}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-white/15 text-xs disabled:opacity-40"
        >
          <Plus size={12} /> Add
        </button>
      </div>

      {error ? <p className="text-xs text-rose-300 break-all">{error}</p> : null}
      <p className="text-[11px] text-muted-foreground">
        Counts time the app is the front window. Idle time after 5 minutes is left out. The budget
        stays in force on a free day and resets at midnight.
        {!freeDay ? " Change this list on a free day or a day pass." : ""}
      </p>
    </div>
  );
}

export default AppTimeLimitsPanel;
