/**
 * Unified Blocks board: one table for sites + apps.
 * SoftLand ≠ Arm — rows write softland.patch_site_rules or arm.set (exes), never one engine.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowDownAZ, ArrowUpAZ, Loader2, Plus, Save, Trash2 } from "lucide-react";
import {
  fetchFocusDashboard,
  putEnforcerPolicy,
  saveSoftLandSiteRules,
  type SoftLandSiteRules,
  type FocusDashboardSnapshot,
} from "../../api/behaviorClient";
import { useFocusStatus, useFreeDay } from "../../hooks/useFocusStatus";
import { softlandSurgeryOpen } from "../../lib/dayGate";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { focusDataUrl } from "../../utils/focusDataUrl";
import { formatHoursMinsFromSeconds } from "../../utils/formatDuration";
import { cn } from "../../app/components/ui/utils";
import { SOFTLAND_LADDER_ONE_LINER } from "./SoftLandSiteRulesPanel";

type Kind = "site" | "app";
/** Board columns — map to SoftLand / Arm as documented. */
type Mode = "focus" | "normal" | "block_fully";
type SortKey = "name" | "used" | "limit" | "kind";
type FilterKey = "all" | "sites" | "apps" | "limited" | "used";

type BoardRow = {
  id: string;
  kind: Kind;
  label: string;
  mode: Mode;
  /** Daily minutes for apps only; null = no time limit. Sites always null. */
  limitMinutes: number | null;
};

type LimitsDoc = {
  enabled?: boolean;
  limits?: { exe?: string; daily_minutes?: number }[];
  usage?: { exe?: string; used_seconds?: number }[];
};

const EMPTY_RULES: SoftLandSiteRules = {
  allow_extra: [],
  watch_extra: [],
  block_extra: [],
};

const MODE_COLS: { id: Mode; label: string; hint: string }[] = [
  { id: "focus", label: "Focus", hint: "Site: study-only. App: kill when Armed." },
  { id: "normal", label: "Normal", hint: "Site: SoftLand allow. App: off kill list." },
  { id: "block_fully", label: "Block fully", hint: "Site: always blocked. App: on kill list." },
];

const FILTERS: { id: FilterKey; label: string }[] = [
  { id: "all", label: "All" },
  { id: "sites", label: "Sites" },
  { id: "apps", label: "Apps" },
  { id: "limited", label: "With limit" },
  { id: "used", label: "Used today" },
];

/** Quick-add strip — common Focus distractions. */
export const TOP_SITES: { id: string; label: string }[] = [
  { id: "youtube.com", label: "YouTube" },
  { id: "reddit.com", label: "Reddit" },
  { id: "twitch.tv", label: "Twitch" },
  { id: "netflix.com", label: "Netflix" },
  { id: "x.com", label: "X" },
  { id: "instagram.com", label: "Instagram" },
  { id: "tiktok.com", label: "TikTok" },
  { id: "facebook.com", label: "Facebook" },
];

export const TOP_APPS: { id: string; label: string }[] = [
  { id: "steam.exe", label: "Steam" },
  { id: "discord.exe", label: "Discord" },
  { id: "spotify.exe", label: "Spotify" },
  { id: "robloxplayerbeta.exe", label: "Roblox" },
  { id: "epicgameslauncher.exe", label: "Epic" },
  { id: "battle.net.exe", label: "Battle.net" },
  { id: "riotclientservices.exe", label: "Riot" },
  { id: "valorant.exe", label: "Valorant" },
];

function asStringList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.map((x) => String(x || "").trim().toLowerCase()).filter(Boolean);
}

function normalizeDomain(raw: string): string {
  let s = raw.trim().toLowerCase().replace(/^https?:\/\//, "");
  s = s.split("/")[0] || "";
  if (s.startsWith("www.")) s = s.slice(4);
  return s;
}

function normalizeExe(raw: string): string {
  let s = raw.trim().toLowerCase();
  if (!s) return "";
  if (!s.endsWith(".exe")) s = `${s}.exe`;
  return s;
}

function looksLikeExe(raw: string): boolean {
  const s = raw.trim().toLowerCase();
  return s.endsWith(".exe") || (!s.includes(".") && /^[a-z0-9_-]+$/i.test(s));
}

async function loadSiteRules(): Promise<SoftLandSiteRules> {
  if (isFocusDesktopShell()) {
    const r = await fetch(focusDataUrl("softland_policy.json"), { cache: "no-store" });
    if (!r.ok) throw new Error(`SoftLand mirror unavailable (${r.status})`);
    const j = (await r.json()) as {
      site_rules?: Partial<SoftLandSiteRules>;
      allow_extra?: string[];
      watch_extra?: string[];
      block_extra?: string[];
    };
    const sr = j.site_rules || j;
    return {
      allow_extra: asStringList(sr.allow_extra),
      watch_extra: asStringList(sr.watch_extra),
      block_extra: asStringList(sr.block_extra),
    };
  }
  const { fetchSoftLandSiteRules } = await import("../../api/behaviorClient");
  return fetchSoftLandSiteRules();
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

function siteModeToLists(rows: BoardRow[]): SoftLandSiteRules {
  const next: SoftLandSiteRules = {
    allow_extra: [],
    watch_extra: [],
    block_extra: [],
  };
  for (const row of rows) {
    if (row.kind !== "site") continue;
    const host = row.label;
    if (row.mode === "normal") next.allow_extra = [...(next.allow_extra || []), host];
    else if (row.mode === "focus") next.watch_extra = [...(next.watch_extra || []), host];
    else next.block_extra = [...(next.block_extra || []), host];
  }
  return next;
}

function appExesFromRows(rows: BoardRow[]): string[] {
  // Focus and Block fully both mean on kill list (Arm has no SoftLand modes).
  return rows
    .filter((r) => r.kind === "app" && (r.mode === "focus" || r.mode === "block_fully"))
    .map((r) => r.label);
}

function appLimitsFromRows(rows: BoardRow[]): { exe: string; daily_minutes: number }[] {
  return rows
    .filter((r) => r.kind === "app" && r.limitMinutes != null && r.limitMinutes > 0)
    .map((r) => ({
      exe: r.label,
      daily_minutes: Math.max(1, Math.min(1440, Math.round(r.limitMinutes!))),
    }));
}

/** Today's used seconds keyed by board row id (`site:host` / `app:exe`). */
async function loadUsedSecondsMap(): Promise<Map<string, number>> {
  const map = new Map<string, number>();
  try {
    const limRes = await fetch(focusDataUrl("app_limits.json"), { cache: "no-store" });
    if (limRes.ok) {
      const lim = (await limRes.json()) as LimitsDoc;
      for (const u of lim.usage || []) {
        const exe = normalizeExe(String(u.exe || ""));
        const sec = Math.max(0, Number(u.used_seconds) || 0);
        if (exe && sec > 0) map.set(`app:${exe}`, sec);
      }
    }
  } catch {
    /* optional */
  }
  try {
    const actRes = await fetch(focusDataUrl("day_activities.json"), { cache: "no-store" });
    if (actRes.ok) {
      const act = (await actRes.json()) as {
        activities?: { label?: string; seconds?: number }[];
      };
      for (const a of act.activities || []) {
        const label = String(a.label || "").toLowerCase().trim();
        const sec = Math.max(0, Number(a.seconds) || 0);
        if (!label || sec <= 0) continue;
        if (label.endsWith(".exe") && !label.includes(":")) {
          const key = `app:${normalizeExe(label)}`;
          map.set(key, Math.max(map.get(key) || 0, sec));
          continue;
        }
        // Tracker form msedge:youtube.com → site:youtube.com
        const colon = label.indexOf(":");
        if (colon > 0) {
          const host = normalizeDomain(label.slice(colon + 1));
          if (host.includes(".")) {
            const key = `site:${host}`;
            map.set(key, Math.max(map.get(key) || 0, sec));
          }
        }
      }
    }
  } catch {
    /* optional */
  }
  return map;
}

export function BlocksBoardPanel() {
  const freeDay = useFreeDay();
  const status = useFocusStatus();
  const canEditSites = softlandSurgeryOpen(status, freeDay);
  const [rows, setRows] = useState<BoardRow[]>([]);
  const [snap, setSnap] = useState<FocusDashboardSnapshot | null>(null);
  const [draft, setDraft] = useState("");
  const [draftMode, setDraftMode] = useState<Mode>("focus");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [limitsEnabled, setLimitsEnabled] = useState(false);
  const [usedById, setUsedById] = useState<Map<string, number>>(() => new Map());
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortAsc, setSortAsc] = useState(true);
  const [filter, setFilter] = useState<FilterKey>("all");

  const passwordLocked = killListLockedFrom(snap);
  const canEditApps = freeDay && !passwordLocked;
  const canSave = canEditSites || canEditApps;

  const refreshUsed = useCallback(async () => {
    try {
      setUsedById(await loadUsedSecondsMap());
    } catch {
      /* keep last */
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let siteRules = EMPTY_RULES;
      try {
        siteRules = await loadSiteRules();
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Could not load SoftLand site rules");
      }

      let exes: string[] = [];
      let nextSnap: FocusDashboardSnapshot | null = null;
      try {
        if (isFocusDesktopShell()) {
          const { fetchEnforcerStatusMirror } = await import("../../api/focusMirrors");
          const enf = await fetchEnforcerStatusMirror();
          const polRes = await fetch(focusDataUrl("enforcer_policy.json"), { cache: "no-store" });
          if (polRes.ok) {
            const pol = (await polRes.json()) as {
              exes?: string[];
              hard_block_armed?: boolean;
              lock_mode?: string;
              lock_until_unix?: number;
              gate_locked?: boolean;
              incubation_active?: boolean;
              anti_tamper?: boolean;
            };
            exes = asStringList(pol.exes);
            nextSnap = {
              enforcer_policy: {
                hard_block_armed: Boolean(pol.hard_block_armed ?? enf?.armed),
                gate_locked: Boolean(pol.gate_locked ?? enf?.locked),
                incubation_active: Boolean(pol.incubation_active),
                exes,
                lock_mode: pol.lock_mode,
                lock_until_unix: pol.lock_until_unix,
                anti_tamper: pol.anti_tamper,
              },
              enforcer: { armed: Boolean(enf?.armed), locked: Boolean(enf?.locked) },
            };
          }
        } else {
          nextSnap = await fetchFocusDashboard();
          exes = asStringList(nextSnap.enforcer_policy?.exes);
        }
      } catch {
        /* apps optional on load */
      }
      setSnap(nextSnap);

      const limitByExe = new Map<string, number>();
      let limOn = false;
      try {
        const limRes = await fetch(focusDataUrl("app_limits.json"), { cache: "no-store" });
        if (limRes.ok) {
          const lim = (await limRes.json()) as LimitsDoc;
          limOn = Boolean(lim.enabled);
          for (const row of lim.limits || []) {
            const exe = normalizeExe(String(row.exe || ""));
            const mins = Math.max(1, Math.min(1440, Number(row.daily_minutes) || 60));
            if (exe) limitByExe.set(exe, mins);
          }
        }
      } catch {
        /* empty limits ok */
      }
      setLimitsEnabled(limOn);

      const next: BoardRow[] = [];
      for (const host of siteRules.allow_extra || []) {
        next.push({ id: `site:${host}`, kind: "site", label: host, mode: "normal", limitMinutes: null });
      }
      for (const host of siteRules.watch_extra || []) {
        next.push({ id: `site:${host}`, kind: "site", label: host, mode: "focus", limitMinutes: null });
      }
      for (const host of siteRules.block_extra || []) {
        next.push({
          id: `site:${host}`,
          kind: "site",
          label: host,
          mode: "block_fully",
          limitMinutes: null,
        });
      }
      const seenApp = new Set<string>();
      for (const exe of exes) {
        seenApp.add(exe);
        next.push({
          id: `app:${exe}`,
          kind: "app",
          label: exe,
          mode: "focus",
          limitMinutes: limitByExe.get(exe) ?? null,
        });
      }
      for (const [exe, mins] of limitByExe) {
        if (seenApp.has(exe)) continue;
        next.push({
          id: `app:${exe}`,
          kind: "app",
          label: exe,
          mode: "normal",
          limitMinutes: mins,
        });
      }
      setRows(next);
      setDirty(false);
      void refreshUsed();
    } finally {
      setLoading(false);
    }
  }, [refreshUsed]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const id = window.setInterval(() => void refreshUsed(), 12_000);
    return () => window.clearInterval(id);
  }, [refreshUsed]);

  const setMode = (id: string, mode: Mode) => {
    const row = rows.find((r) => r.id === id);
    if (!row) return;
    if (row.kind === "site" && !canEditSites) return;
    if (row.kind === "app" && !canEditApps) return;
    setRows((cur) => cur.map((r) => (r.id === id ? { ...r, mode } : r)));
    setDirty(true);
    setSaved(false);
  };

  const setLimitMinutes = (id: string, raw: string) => {
    const row = rows.find((r) => r.id === id);
    if (!row || row.kind !== "app" || !canEditApps) return;
    const trimmed = raw.trim();
    let next: number | null = null;
    if (trimmed !== "") {
      const n = Number(trimmed);
      if (!Number.isFinite(n) || n <= 0) next = null;
      else next = Math.max(1, Math.min(1440, Math.round(n)));
    }
    setRows((cur) => cur.map((r) => (r.id === id ? { ...r, limitMinutes: next } : r)));
    setDirty(true);
    setSaved(false);
  };

  const removeRow = (id: string) => {
    const row = rows.find((r) => r.id === id);
    if (!row) return;
    if (row.kind === "site" && !canEditSites) return;
    if (row.kind === "app" && !canEditApps) return;
    setRows((cur) => cur.filter((r) => r.id !== id));
    setDirty(true);
    setSaved(false);
  };

  const pushRow = (kind: Kind, label: string, mode: Mode) => {
    if (kind === "app") {
      if (!canEditApps) {
        setError("App kill list needs a free day / pass (and Arm unlocked).");
        return false;
      }
      const exe = normalizeExe(label);
      if (!exe) return false;
      if (rows.some((r) => r.kind === "app" && r.label === exe)) {
        setError(`${exe} is already on the board.`);
        return false;
      }
      const appMode: Mode = mode === "normal" ? "focus" : mode;
      const presetLimit =
        TOP_APPS.find((a) => normalizeExe(a.id) === exe)?.id === exe
          ? ({ "steam.exe": 60, "discord.exe": 45, "spotify.exe": 90, "robloxplayerbeta.exe": 45 } as Record<
              string,
              number
            >)[exe] ?? null
          : null;
      setRows((cur) => [
        ...cur,
        {
          id: `app:${exe}`,
          kind: "app",
          label: exe,
          mode: appMode,
          limitMinutes: presetLimit,
        },
      ]);
    } else {
      if (!canEditSites) {
        setError(
          "Finish morning Bible" +
            (status.dayLoop?.planning_enabled ? " + Confirm plan" : "") +
            ", or use a free day / day pass.",
        );
        return false;
      }
      const host = normalizeDomain(label);
      if (!host || !host.includes(".")) {
        setError("Enter a domain like youtube.com, or an app like steam.exe");
        return false;
      }
      if (rows.some((r) => r.kind === "site" && r.label === host)) {
        setError(`${host} is already on the board.`);
        return false;
      }
      setRows((cur) => [
        ...cur,
        { id: `site:${host}`, kind: "site", label: host, mode, limitMinutes: null },
      ]);
    }
    setDirty(true);
    setSaved(false);
    setError(null);
    return true;
  };

  const addRow = () => {
    const raw = draft.trim();
    if (!raw) return;
    if (pushRow(looksLikeExe(raw) ? "app" : "site", raw, draftMode)) setDraft("");
  };

  const addPreset = (kind: Kind, id: string) => {
    void pushRow(kind, id, draftMode);
  };

  const onBoard = (kind: Kind, id: string) =>
    rows.some((r) => r.kind === kind && r.label === (kind === "app" ? normalizeExe(id) : normalizeDomain(id)));

  const save = async () => {
    if (!canSave) {
      setError("List edits need a free day / day pass after Confirm.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (canEditSites) {
        const rules = siteModeToLists(rows);
        if (isFocusEnforcerBridgeAvailable()) {
          const res = await enforcerNativeCmd("softland.patch_site_rules", {
            allow_extra: rules.allow_extra || [],
            watch_extra: rules.watch_extra || [],
            block_extra: rules.block_extra || [],
          });
          if (!res?.ok) throw new Error(String(res?.error || "softland.patch_site_rules failed"));
        } else if (isFocusDesktopShell()) {
          throw new Error("SoftLand saves need calt_focus.exe (enforcer pipe).");
        } else {
          await saveSoftLandSiteRules(rules);
        }
      }

      if (canEditApps) {
        const exes = appExesFromRows(rows);
        const pol = snap?.enforcer_policy;
        const stayArmed = Boolean(pol?.hard_block_armed || snap?.enforcer?.armed);
        if (isFocusEnforcerBridgeAvailable()) {
          const res = await enforcerNativeCmd("arm.set", {
            hard_block_armed: stayArmed,
            gate_locked: stayArmed ? Boolean(pol?.gate_locked ?? true) : false,
            incubation_active: Boolean(pol?.incubation_active),
            exes,
            anti_tamper: typeof pol?.anti_tamper === "boolean" ? pol.anti_tamper : true,
            lock_mode: pol?.lock_mode || "none",
          });
          if (!res?.ok) throw new Error(String(res?.error || "arm.set failed"));
        } else {
          await putEnforcerPolicy({
            hard_block_armed: stayArmed,
            gate_locked: stayArmed ? Boolean(pol?.gate_locked ?? true) : false,
            incubation_active: Boolean(pol?.incubation_active),
            exes,
            anti_tamper: typeof pol?.anti_tamper === "boolean" ? pol.anti_tamper : undefined,
          });
        }

        const limits = appLimitsFromRows(rows);
        const enableLimits = limits.length > 0 ? true : limitsEnabled;
        if (isFocusEnforcerBridgeAvailable()) {
          const limRes = await enforcerNativeCmd("app_limits.set", {
            enabled: enableLimits && limits.length > 0,
            limits,
          });
          if (!limRes?.ok) {
            const err = String(limRes?.error || "app_limits.set failed");
            if (err !== "unknown_op" && err !== "free_day_required") {
              throw new Error(err);
            }
            if (err === "free_day_required") throw new Error(err);
          } else {
            setLimitsEnabled(Boolean(enableLimits && limits.length > 0));
          }
        }
      }

      setDirty(false);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2500);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const siteCount = useMemo(() => rows.filter((r) => r.kind === "site").length, [rows]);
  const appCount = useMemo(() => rows.filter((r) => r.kind === "app").length, [rows]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((a) => !a);
    else {
      setSortKey(key);
      setSortAsc(key === "name" || key === "kind");
    }
  };

  const visibleRows = useMemo(() => {
    let list = rows;
    if (filter === "sites") list = list.filter((r) => r.kind === "site");
    else if (filter === "apps") list = list.filter((r) => r.kind === "app");
    else if (filter === "limited")
      list = list.filter((r) => r.kind === "app" && r.limitMinutes != null && r.limitMinutes > 0);
    else if (filter === "used") list = list.filter((r) => (usedById.get(r.id) || 0) > 0);

    const dir = sortAsc ? 1 : -1;
    return [...list].sort((a, b) => {
      if (sortKey === "used") {
        const ua = usedById.get(a.id) || 0;
        const ub = usedById.get(b.id) || 0;
        if (ua !== ub) return (ua - ub) * dir;
      } else if (sortKey === "limit") {
        const la = a.limitMinutes ?? -1;
        const lb = b.limitMinutes ?? -1;
        if (la !== lb) return (la - lb) * dir;
      } else if (sortKey === "kind") {
        if (a.kind !== b.kind) return (a.kind < b.kind ? -1 : 1) * dir;
      }
      const byName = a.label.localeCompare(b.label);
      if (byName !== 0) return byName * (sortKey === "name" ? dir : 1);
      return a.kind.localeCompare(b.kind);
    });
  }, [rows, filter, sortKey, sortAsc, usedById]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-3">
        <Loader2 size={14} className="animate-spin" /> Loading blocks…
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
        <span className="rounded-md border border-border/50 px-2 py-0.5">
          {siteCount} site{siteCount === 1 ? "" : "s"} · {appCount} app{appCount === 1 ? "" : "s"}
          {filter !== "all" ? ` · showing ${visibleRows.length}` : ""}
        </span>
        <span className="text-[11px] text-muted-foreground/80 max-w-xl truncate hidden sm:inline">
          SoftLand ≠ Arm · {SOFTLAND_LADDER_ONE_LINER}
        </span>
        {!canEditSites || !canEditApps ? (
          <span className="rounded-md border border-amber-400/35 bg-amber-500/10 px-2 py-0.5 text-amber-100">
            {!canEditSites && !canEditApps
              ? "Edits need free day / pass"
              : !canEditSites
                ? "Site edits locked"
                : passwordLocked
                  ? "Kill list locked"
                  : "App edits need free day / pass"}
          </span>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter board">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFilter(f.id)}
            className={cn(
              "rounded-full border px-2.5 py-1 text-[11px] transition-colors",
              filter === f.id
                ? "border-[#0B6B63]/60 bg-[#0B6B63]/20 text-foreground"
                : "border-border/40 text-muted-foreground hover:bg-accent/30",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto rounded-xl border border-border/50">
        <table className="w-full min-w-[48rem] border-collapse text-left text-[13px]">
          <thead>
            <tr className="border-b border-border/50 bg-background/30 text-[11px] uppercase tracking-[0.06em] text-muted-foreground">
              <th className="px-3 py-2.5 font-semibold">
                <button
                  type="button"
                  onClick={() => toggleSort("name")}
                  className="inline-flex items-center gap-1 hover:text-foreground"
                >
                  App / website
                  {sortKey === "name" ? (
                    sortAsc ? (
                      <ArrowUpAZ size={12} className="opacity-80" aria-hidden />
                    ) : (
                      <ArrowDownAZ size={12} className="opacity-80" aria-hidden />
                    )
                  ) : null}
                </button>
              </th>
              {MODE_COLS.map((c) => (
                <th key={c.id} className="px-2 py-2.5 font-semibold text-center w-[6.5rem]" title={c.hint}>
                  {c.label}
                </th>
              ))}
              <th
                className="px-2 py-2.5 font-semibold text-center w-[5rem]"
                title="Today’s front-window time from tracker / limits."
              >
                <button
                  type="button"
                  onClick={() => toggleSort("used")}
                  className="inline-flex items-center gap-1 hover:text-foreground"
                >
                  Used
                  {sortKey === "used" ? (
                    sortAsc ? (
                      <ArrowUpAZ size={12} className="opacity-80" aria-hidden />
                    ) : (
                      <ArrowDownAZ size={12} className="opacity-80" aria-hidden />
                    )
                  ) : null}
                </button>
              </th>
              <th
                className="px-2 py-2.5 font-semibold text-center w-[5.5rem]"
                title="Daily front-window minutes for apps. Empty = no budget. Sites use SoftLand, not minutes."
              >
                <button
                  type="button"
                  onClick={() => toggleSort("limit")}
                  className="inline-flex items-center gap-1 hover:text-foreground"
                >
                  Limit
                  {sortKey === "limit" ? (
                    sortAsc ? (
                      <ArrowUpAZ size={12} className="opacity-80" aria-hidden />
                    ) : (
                      <ArrowDownAZ size={12} className="opacity-80" aria-hidden />
                    )
                  ) : null}
                </button>
              </th>
              <th className="px-2 py-2.5 w-10" aria-label="Remove" />
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-muted-foreground">
                  Empty — tap a chip below or type a domain / .exe.
                </td>
              </tr>
            ) : visibleRows.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-muted-foreground">
                  No rows match this filter.
                </td>
              </tr>
            ) : (
              visibleRows.map((row) => {
                const rowLocked =
                  (row.kind === "site" && !canEditSites) || (row.kind === "app" && !canEditApps);
                const usedSec = usedById.get(row.id) || 0;
                return (
                  <tr key={row.id} className="border-b border-border/30 last:border-0">
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className={cn(
                            "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                            row.kind === "site"
                              ? "border border-sky-400/30 bg-sky-500/10 text-sky-100"
                              : "border border-rose-400/30 bg-rose-500/10 text-rose-100",
                          )}
                        >
                          {row.kind}
                        </span>
                        <span className="truncate font-mono text-[12px] text-foreground/90">
                          {row.label}
                        </span>
                      </div>
                    </td>
                    {MODE_COLS.map((c) => (
                      <td key={c.id} className="px-2 py-2 text-center">
                        <input
                          type="radio"
                          name={`mode-${row.id}`}
                          checked={row.mode === c.id}
                          disabled={rowLocked}
                          onChange={() => setMode(row.id, c.id)}
                          className="accent-[#0B6B63]"
                          aria-label={`${row.label} ${c.label}`}
                        />
                      </td>
                    ))}
                    <td className="px-2 py-2 text-center tabular-nums text-[12px] text-foreground/85">
                      {usedSec > 0 ? (
                        formatHoursMinsFromSeconds(usedSec)
                      ) : (
                        <span className="text-muted-foreground/50">—</span>
                      )}
                    </td>
                    <td className="px-2 py-2 text-center">
                      {row.kind === "site" ? (
                        <span className="text-[11px] text-muted-foreground/60">—</span>
                      ) : (
                        <input
                          type="number"
                          min={1}
                          max={1440}
                          placeholder="—"
                          disabled={rowLocked}
                          value={row.limitMinutes ?? ""}
                          onChange={(e) => setLimitMinutes(row.id, e.target.value)}
                          className="w-14 rounded border border-border/40 bg-background/40 px-1.5 py-1 text-center text-[12px] tabular-nums disabled:opacity-40"
                          aria-label={`${row.label} daily minutes`}
                          title="Minutes/day (front window). Clear for no limit."
                        />
                      )}
                    </td>
                    <td className="px-2 py-2 text-center">
                      <button
                        type="button"
                        disabled={rowLocked}
                        onClick={() => removeRow(row.id)}
                        className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-rose-500/15 hover:text-rose-200 disabled:opacity-30"
                        aria-label={`Remove ${row.label}`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[12px] font-medium text-foreground/90">Top sites</p>
          <select
            value={draftMode}
            onChange={(e) => setDraftMode(e.target.value as Mode)}
            className="rounded-md border border-border/50 bg-background/40 px-2 py-1 text-[11px]"
            title={MODE_COLS.find((c) => c.id === draftMode)?.hint}
          >
            {MODE_COLS.map((c) => (
              <option key={c.id} value={c.id}>
                Add as {c.label}
              </option>
            ))}
          </select>
        </div>
        <div
          className="flex gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          role="list"
          aria-label="Top sites"
        >
          {TOP_SITES.map((s) => {
            const used = onBoard("site", s.id);
            return (
              <button
                key={s.id}
                type="button"
                role="listitem"
                disabled={used || !canEditSites}
                onClick={() => addPreset("site", s.id)}
                className={cn(
                  "shrink-0 rounded-full border px-3 py-1.5 text-[12px] transition-colors",
                  used
                    ? "border-border/30 text-muted-foreground/50"
                    : "border-sky-400/35 bg-sky-500/10 text-sky-50 hover:bg-sky-500/20 disabled:opacity-40",
                )}
              >
                {used ? "✓ " : "+ "}
                {s.label}
              </button>
            );
          })}
        </div>
        <p className="text-[12px] font-medium text-foreground/90 pt-1">Top apps</p>
        <div
          className="flex gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          role="list"
          aria-label="Top apps"
        >
          {TOP_APPS.map((a) => {
            const used = onBoard("app", a.id);
            return (
              <button
                key={a.id}
                type="button"
                role="listitem"
                disabled={used || !canEditApps}
                onClick={() => addPreset("app", a.id)}
                className={cn(
                  "shrink-0 rounded-full border px-3 py-1.5 text-[12px] transition-colors",
                  used
                    ? "border-border/30 text-muted-foreground/50"
                    : "border-rose-400/35 bg-rose-500/10 text-rose-50 hover:bg-rose-500/20 disabled:opacity-40",
                )}
              >
                {used ? "✓ " : "+ "}
                {a.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addRow();
            }
          }}
          placeholder="youtube.com or steam.exe"
          className="min-w-[12rem] flex-1 rounded-lg border border-border/50 bg-background/40 px-3 py-2 text-sm"
        />
        <button
          type="button"
          onClick={addRow}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-border/50 bg-background/40 px-3 text-sm hover:bg-accent/40"
        >
          <Plus size={14} /> Add
        </button>
        <button
          type="button"
          disabled={saving || !dirty || !canSave}
          onClick={() => void save()}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-[#0B6B63] bg-[#0B6B63] px-4 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          {saving ? "Saving…" : saved ? "Saved" : "Save"}
        </button>
      </div>

      {error ? <p className="text-[12px] text-rose-300">{error}</p> : null}
    </div>
  );
}

export default BlocksBoardPanel;
