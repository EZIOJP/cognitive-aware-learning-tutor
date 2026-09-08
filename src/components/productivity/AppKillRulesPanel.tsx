import { useCallback, useEffect, useState } from "react";
import { Ban, Plus, Save, Shield } from "lucide-react";
import {
  fetchFocusDashboard,
  putEnforcerPolicy,
  type FocusDashboardSnapshot,
} from "../../api/behaviorClient";

/** Sensible subsets matching DEFAULT_HARD_BLOCK_EXES / Focus defaults. */
const PRESETS: Record<string, string[]> = {
  Gaming: [
    "steam.exe",
    "steamwebhelper.exe",
    "epicgameslauncher.exe",
    "epicwebhelper.exe",
    "riotclientservices.exe",
    "leagueclient.exe",
    "valorant.exe",
    "minecraft.exe",
    "minecraftlauncher.exe",
    "robloxplayerbeta.exe",
    "battle.net.exe",
    "eadesktop.exe",
    "origin.exe",
    "ubisoftconnect.exe",
    "xboxapp.exe",
    "gamebar.exe",
  ],
  Social: [
    "discord.exe",
    "discordptb.exe",
    "discordcanary.exe",
    "spotify.exe",
    "twitch.exe",
    "netflix.exe",
    "primevideo.exe",
    "disneyplus.exe",
    "hulu.exe",
  ],
};

function normalizeExe(raw: string): string {
  let s = raw.trim().toLowerCase();
  if (!s) return "";
  if (!s.endsWith(".exe")) s = `${s}.exe`;
  return s;
}

function killListLockedFrom(snap: FocusDashboardSnapshot | null): boolean {
  const pol = snap?.enforcer_policy;
  if (!pol?.hard_block_armed) return false;
  const lockModeActive = String(pol.lock_mode || "none").toLowerCase();
  if (lockModeActive === "none") return false;
  const timerStillActive =
    lockModeActive === "timer" &&
    typeof pol.lock_until_unix === "number" &&
    pol.lock_until_unix > Math.floor(Date.now() / 1000);
  return (
    lockModeActive === "password" ||
    lockModeActive === "phrase" ||
    timerStillActive ||
    (lockModeActive === "timer" && !pol.lock_until_unix)
  );
}

export function AppKillRulesPanel() {
  const [snap, setSnap] = useState<FocusDashboardSnapshot | null>(null);
  const [exes, setExes] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const s = await fetchFocusDashboard();
      setSnap(s);
      setExes(list(s.enforcer_policy?.exes));
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load kill list");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const locked = killListLockedFrom(snap);
  const armed = Boolean(snap?.enforcer_policy?.hard_block_armed || snap?.enforcer?.armed);

  const addExe = (raw: string) => {
    const name = normalizeExe(raw);
    if (!name || locked) return;
    setExes((cur) => (cur.some((x) => x === name) ? cur : [...cur, name]));
    setSaved(false);
  };

  const removeExe = (name: string) => {
    if (locked) return;
    setExes((cur) => cur.filter((x) => x !== name));
    setSaved(false);
  };

  const applyPreset = (key: string) => {
    if (locked) return;
    const list = PRESETS[key] || [];
    setExes((cur) => {
      const set = new Set(cur);
      for (const exe of list) set.add(exe);
      return [...set];
    });
    setSaved(false);
  };

  const save = async () => {
    if (!snap || locked) return;
    setSaving(true);
    setError(null);
    try {
      const pol = snap.enforcer_policy;
      const stayArmed = Boolean(pol?.hard_block_armed);
      const res = await putEnforcerPolicy({
        hard_block_armed: stayArmed,
        gate_locked: stayArmed ? Boolean(pol?.gate_locked ?? true) : false,
        incubation_active: Boolean(pol?.incubation_active),
        exes,
        anti_tamper: typeof pol?.anti_tamper === "boolean" ? pol.anti_tamper : undefined,
      });
      setSnap(res.snapshot);
      const nextExes = res.snapshot.enforcer_policy?.exes;
      setExes(list(nextExes ?? (Array.isArray(res.policy.exes) ? (res.policy.exes as string[]) : [])));
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-sm flex items-center gap-2">
            <Ban size={16} className="text-rose-300" />
            App kill rules
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            OS process kill list for{" "}
            <code className="text-foreground/80">calt_enforcer</code>
            {armed ? " · currently Armed" : " · Disarmed"}. SoftLand sites are separate.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving || locked}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/70 hover:bg-emerald-600 text-xs disabled:opacity-50"
        >
          <Save size={12} /> {saving ? "Saving…" : saved ? "Saved" : "Save"}
        </button>
      </div>

      {locked ? (
        <p className="text-xs text-amber-200/90">
          Kill list locked while armed with password/phrase/timer — disarm on{" "}
          <a className="underline" href="#focus">
            Focus
          </a>{" "}
          to edit.
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {Object.keys(PRESETS).map((key) => (
          <button
            key={key}
            type="button"
            disabled={locked}
            onClick={() => applyPreset(key)}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-white/15 text-[11px] hover:bg-white/5 disabled:opacity-40"
          >
            <Shield size={11} /> Add {key} preset
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-1.5 min-h-[1.5rem]">
        {exes.length === 0 ? (
          <span className="text-[11px] text-muted-foreground">No exes yet — add or use a preset.</span>
        ) : (
          exes.map((exe) => (
            <button
              key={exe}
              type="button"
              disabled={locked}
              onClick={() => removeExe(exe)}
              className="text-[10px] px-2 py-0.5 rounded border border-rose-400/30 bg-rose-500/10 hover:border-rose-400/60 disabled:opacity-40"
              title="Remove"
            >
              {exe} ×
            </button>
          ))
        )}
      </div>

      <div className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addExe(draft);
              setDraft("");
            }
          }}
          disabled={locked}
          placeholder="e.g. steam.exe"
          className="flex-1 rounded border border-white/10 bg-black/30 px-2 py-1.5 text-xs disabled:opacity-50"
        />
        <button
          type="button"
          disabled={locked || !draft.trim()}
          onClick={() => {
            addExe(draft);
            setDraft("");
          }}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-white/15 text-xs disabled:opacity-40"
        >
          <Plus size={12} /> Add
        </button>
      </div>

      {error ? <p className="text-xs text-rose-300 break-all">{error}</p> : null}
      <p className="text-[11px] text-muted-foreground">
        Writes <code className="text-foreground/80">enforcer_policy.json</code>. Arm/disarm stays on{" "}
        <a className="underline text-sky-300/90" href="#focus">
          Focus
        </a>
        .
      </p>
    </div>
  );
}

function list(exes: string[] | undefined): string[] {
  return Array.isArray(exes) ? [...exes] : [];
}

export default AppKillRulesPanel;
