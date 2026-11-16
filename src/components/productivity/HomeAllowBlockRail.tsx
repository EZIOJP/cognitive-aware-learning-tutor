import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { endOfDay, startOfDay, subDays } from "date-fns";
import {
  Ban,
  Clock3,
  Coffee,
  Globe,
  GripVertical,
  Minus,
  Play,
  Plus,
  ShieldCheck,
  Sparkles,
  Square,
  X,
} from "lucide-react";
import { suggestSessionLists } from "../../lib/focusLlmHost";
import { putEnforcerPolicy } from "../../api/behaviorClient";
import { fetchActualOverlay, type ActualSession } from "../../api/plannerClient";
import { useFreeDay } from "../../hooks/useFocusStatus";
import { isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { focusDataUrl } from "../../utils/focusDataUrl";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { formatHoursMinsFromSeconds } from "../../utils/formatDuration";
import { cn } from "../../app/components/ui/utils";
import { WORK_SESSION_UPDATED_EVENT } from "./workSessionEvents";
export { WORK_SESSION_UPDATED_EVENT };

type Zone = "pool" | "allow" | "block";
type ChipKind = "app" | "site";

type UsageChip = {
  kind: ChipKind;
  id: string;
  label: string;
  seconds: number;
};

type SessionDoc = {
  active?: boolean;
  started_at?: string;
  ends_at?: string;
  apps?: string[];
  sites?: string[];
};

const MIME = "application/x-calt-home-usage";

const DURATION_PRESETS = [
  { minutes: 25, label: "25m", rest: 5 },
  { minutes: 50, label: "50m", rest: 10 },
  { minutes: 90, label: "90m", rest: 15 },
  { minutes: 0, label: "Open", rest: 0 },
];

const NEAR_END_SEC = 3 * 60;

const BROWSERS = new Set([
  "chrome.exe",
  "msedge.exe",
  "msedgewebview2.exe",
  "firefox.exe",
  "brave.exe",
  "opera.exe",
  "vivaldi.exe",
  "iexplore.exe",
  "arc.exe",
  "zen.exe",
  "chromium.exe",
]);

const PROTECTED = new Set([
  "explorer.exe",
  "calt_focus.exe",
  "calt_enforcer.exe",
  "calt_msg_host.exe",
  "dwm.exe",
  "taskmgr.exe",
  "systemsettings.exe",
  "searchhost.exe",
  "startmenuexperiencehost.exe",
  "shellexperiencehost.exe",
  "amazfit.exe",
]);

const LABEL_HINTS: Record<string, string> = {
  "steam.exe": "Steam",
  "steamwebhelper.exe": "Steam Helper",
  "discord.exe": "Discord",
  "discordptb.exe": "Discord PTB",
  "discordcanary.exe": "Discord Canary",
  "robloxplayerbeta.exe": "Roblox",
  "spotify.exe": "Spotify",
  "cursor.exe": "Cursor",
  "code.exe": "VS Code",
  "notion.exe": "Notion",
  "valorant.exe": "Valorant",
  "leagueclient.exe": "League",
  "minecraftlauncher.exe": "Minecraft",
  "minecraft.exe": "Minecraft",
  "epicgameslauncher.exe": "Epic",
  "riotclientservices.exe": "Riot",
  "battle.net.exe": "Battle.net",
  "netflix.exe": "Netflix",
  "winword.exe": "Word",
  "excel.exe": "Excel",
  "powerpnt.exe": "PowerPoint",
  "outlook.exe": "Outlook",
  "onenote.exe": "OneNote",
  "slack.exe": "Slack",
  "teams.exe": "Teams",
  "figma.exe": "Figma",
  "obsidian.exe": "Obsidian",
};

const PRODUCTIVITY_APPS: string[] = [
  "cursor.exe",
  "code.exe",
  "winword.exe",
  "excel.exe",
  "notion.exe",
  "obsidian.exe",
  "slack.exe",
  "teams.exe",
  "figma.exe",
  "onenote.exe",
];

const PRODUCTIVITY_SITES: string[] = [
  "github.com",
  "docs.google.com",
  "stackoverflow.com",
  "notion.so",
  "linear.app",
  "figma.com",
  "chatgpt.com",
  "claude.ai",
];

function normalizeExe(raw: string): string {
  let s = raw.trim().toLowerCase();
  // Tracker form "msedge:youtube.com" — take browser side only.
  if (s.includes(":") && !s.includes("\\") && !s.includes("/")) {
    const left = s.split(":")[0] || "";
    if (BROWSERS.has(left.endsWith(".exe") ? left : `${left}.exe`) || left === "selftracker") {
      s = left;
    }
  }
  if (!s || s.includes("\\") || s.includes("/") || s.includes(":")) {
    const base = s.split(/[/\\]/).pop() || "";
    s = base.trim().toLowerCase();
  }
  if (!s) return "";
  if (!s.endsWith(".exe")) s = `${s}.exe`;
  if (!/^[a-z0-9][a-z0-9._-]{0,59}\.exe$/.test(s)) return "";
  return s;
}

function normalizeSite(raw: string): string {
  let s = raw.trim().toLowerCase();
  s = s.replace(/^[a-z]+:\/\//, "");
  // Tracker form "msedge:youtube.com" → youtube.com
  {
    const colon = s.lastIndexOf(":");
    if (colon > 0 && !s.includes("/") && !s.includes("\\")) {
      const left = s.slice(0, colon).replace(/\.exe$/i, "");
      const right = s.slice(colon + 1);
      if (
        (BROWSERS.has(`${left}.exe`) || left === "selftracker") &&
        right.includes(".")
      ) {
        s = right;
      }
    }
  }
  s = s.split("/")[0]?.split("?")[0]?.split("#")[0] ?? "";
  // Strip accidental port only (host:443), not browser:host (handled above).
  if (/^\d+$/.test(s.split(":").pop() || "")) {
    s = s.split(":")[0] ?? s;
  }
  if (s.startsWith("www.")) s = s.slice(4);
  if (!/^[a-z0-9][a-z0-9.-]{1,78}\.[a-z]{2,}$/.test(s)) return "";
  return s;
}

function looksLikeDomain(value: string | null | undefined): boolean {
  const v = (value || "").trim().toLowerCase();
  if (!v || /\s/.test(v) || v.endsWith(".exe") || v.startsWith("calt_spa")) return false;
  return v.includes(".");
}

function siteFromTitle(title: string | null | undefined): string {
  const t = String(title || "").trim();
  if (!t) return "";
  // Prefer an explicit host token in the title.
  const hostMatch = t.match(/\b(?:https?:\/\/)?(?:www\.)?([a-z0-9][a-z0-9.-]+\.[a-z]{2,})\b/i);
  if (hostMatch?.[1]) {
    const host = normalizeSite(hostMatch[1]);
    if (host) return host;
  }
  return "";
}

function labelForExe(exe: string): string {
  if (LABEL_HINTS[exe]) return LABEL_HINTS[exe];
  const stem = exe.replace(/\.exe$/i, "");
  return stem
    .split(/[._-]+/)
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}

function productivitySeedChips(): UsageChip[] {
  return [
    ...PRODUCTIVITY_APPS.map((id) => ({
      kind: "app" as const,
      id,
      label: labelForExe(id),
      seconds: 0,
    })),
    ...PRODUCTIVITY_SITES.map((id) => ({
      kind: "site" as const,
      id,
      label: id,
      seconds: 0,
    })),
  ];
}

function explain(err: string): string {
  switch (err) {
    case "free_day_required":
      return "Edit Allow / Block on a free day or a day pass.";
    case "enforcer_unreachable":
      return "Open CALT Focus so the enforcer can save.";
    case "protected_exe":
      return "Windows and CALT stay available on their own.";
    case "browser_exe":
      return "Browsers stay under Sites on Allow.";
    case "site_not_blockable":
      return "Sites go on Allow (session), not Arm Block.";
    case "empty_session":
      return "Add at least one program or website before starting.";
    case "bad_exe":
      return "Use a program name like cursor.exe.";
    case "bad_site":
      return "Use a site like github.com.";
    case "too_many":
      return "24 programs and 24 sites is the maximum.";
    case "bad_minutes":
      return "Session length must be between 1 and 720 minutes, or until you stop.";
    case "session_write_failed":
      return "Couldn't save the session. Check that the enforcer is running.";
    case "unknown_op":
      return "Restart the enforcer so SoftLand / Arm writes work.";
    case "timeout":
      return "The enforcer didn't answer. Try again.";
    default:
      return err || "Couldn't save";
  }
}

function endsLabel(ends: string | undefined): string {
  if (!ends) return "Until you end it";
  const m = ends.match(/T(\d{2}:\d{2})/);
  return m ? `Until ${m[1]}` : ends;
}

function summaryLine(apps: string[], sites: string[], minutes: number): string {
  const bits: string[] = [];
  if (minutes > 0) bits.push(`${minutes}m`);
  else bits.push("Open length");
  if (apps.length) bits.push(`${apps.length} app${apps.length === 1 ? "" : "s"}`);
  if (sites.length) bits.push(`${sites.length} site${sites.length === 1 ? "" : "s"}`);
  if (!apps.length && !sites.length) bits.push("No allowlist yet");
  return bits.join(" · ");
}

function formatDigital(totalMinutes: number): string {
  if (totalMinutes <= 0) return "∞";
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:00`;
}

function formatCountdown(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return "00:00";
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function remainingMs(endsAt: string | undefined): number | null {
  if (!endsAt) return null;
  const t = Date.parse(endsAt);
  if (!Number.isFinite(t)) return null;
  return t - Date.now();
}

function SessionTimerDialog({
  open,
  onClose,
  freeDay,
  sessionActive,
  minutes,
  endsAt,
  restMinutes,
  onChangeMinutes,
  onChangeRest,
  onExtend,
  onTakeRest,
  onStart,
  canStart,
  busy,
}: {
  open: boolean;
  onClose: () => void;
  freeDay: boolean;
  sessionActive: boolean;
  minutes: number;
  endsAt: string;
  restMinutes: number;
  onChangeMinutes: (m: number) => void;
  onChangeRest: (m: number) => void;
  onExtend: (extra: number) => void;
  onTakeRest: () => void;
  onStart: () => void;
  canStart: boolean;
  busy: boolean;
}) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!open) return;
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, [open]);

  if (!open) return null;

  const left = sessionActive ? remainingMs(endsAt) : null;
  const nearEnd =
    sessionActive && left != null && left > 0 && left <= NEAR_END_SEC * 1000;
  const liveDisplay = sessionActive
    ? left == null
      ? "∞"
      : formatCountdown(Math.max(0, (Date.parse(endsAt) || 0) - now))
    : formatDigital(minutes);

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-end justify-center bg-black/55 p-3 pb-4 sm:p-4 sm:pb-6 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-label="Focus timer"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md max-h-[min(85vh,40rem)] overflow-y-auto rounded-2xl border border-border/50 bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border/40 px-4 py-2.5">
          <div className="flex items-center gap-2">
            <Clock3 className="size-4 text-emerald-300/90" aria-hidden />
            <p className="text-sm font-medium">Focus timer</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-muted-foreground hover:bg-white/5 hover:text-foreground"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <div className="space-y-4 px-4 py-4">
          <div className="rounded-xl border border-white/10 bg-black/40 px-4 py-5 text-center">
            <p
              className={cn(
                "font-semibold tabular-nums tracking-tight leading-none",
                liveDisplay.length > 5 ? "text-4xl" : "text-5xl",
                nearEnd ? "text-amber-200" : "text-emerald-100",
              )}
            >
              {liveDisplay}
            </p>
            <p className="mt-2 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
              {sessionActive
                ? nearEnd
                  ? "Wrapping up"
                  : endsAt
                    ? "Time left"
                    : "Open session"
                : minutes > 0
                  ? "Focus length"
                  : "Until you stop"}
            </p>
          </div>

          {nearEnd ? (
            <p className="rounded-lg border border-amber-400/25 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-50/95">
              Focus is nearly up — pause video and park work so you finish cleanly, then extend or take a rest.
            </p>
          ) : (
            <p className="text-[12px] text-muted-foreground">
              Find your natural rhythm: set a focus block, then extend a little or rest when the clock softens.
            </p>
          )}

          {!sessionActive ? (
            <>
              <div>
                <p className="mb-1.5 text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  Length
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    disabled={busy || minutes <= 0}
                    onClick={() => onChangeMinutes(Math.max(5, (minutes || 25) - 5))}
                    className="rounded-lg border border-white/15 p-2 disabled:opacity-40"
                    aria-label="Minus 5 minutes"
                  >
                    <Minus size={14} />
                  </button>
                  <div className="flex flex-wrap gap-1">
                    {DURATION_PRESETS.map((d) => (
                      <button
                        key={d.label}
                        type="button"
                        disabled={busy}
                        onClick={() => {
                          onChangeMinutes(d.minutes);
                          if (d.rest) onChangeRest(d.rest);
                        }}
                        className={cn(
                          "rounded-lg border px-2.5 py-1 text-[11px] disabled:opacity-40",
                          minutes === d.minutes
                            ? "border-emerald-400/50 bg-emerald-500/15 text-emerald-100"
                            : "border-white/15 text-muted-foreground hover:bg-white/5",
                        )}
                      >
                        {d.label === "Open" ? "Until I stop" : d.label}
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    disabled={busy || minutes <= 0 || minutes >= 720}
                    onClick={() => onChangeMinutes(Math.min(720, (minutes || 25) + 5))}
                    className="rounded-lg border border-white/15 p-2 disabled:opacity-40"
                    aria-label="Plus 5 minutes"
                  >
                    <Plus size={14} />
                  </button>
                </div>
              </div>

              <div>
                <p className="mb-1.5 text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  Pomodoro rest after focus
                </p>
                <div className="flex flex-wrap gap-1">
                  {[0, 5, 10, 15].map((r) => (
                    <button
                      key={r}
                      type="button"
                      disabled={busy || minutes <= 0}
                      onClick={() => onChangeRest(r)}
                      className={cn(
                        "rounded-lg border px-2.5 py-1 text-[11px] disabled:opacity-40",
                        restMinutes === r
                          ? "border-sky-400/45 bg-sky-500/15 text-sky-100"
                          : "border-white/15 text-muted-foreground hover:bg-white/5",
                      )}
                    >
                      {r === 0 ? "No rest" : `${r}m rest`}
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => onExtend(5)}
                className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-2 py-2.5 text-[12px] text-emerald-50 disabled:opacity-40"
              >
                +5 min
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => onExtend(10)}
                className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-2 py-2.5 text-[12px] text-emerald-50 disabled:opacity-40"
              >
                +10 min
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => onTakeRest()}
                className="inline-flex items-center justify-center gap-1 rounded-xl border border-sky-400/30 bg-sky-500/10 px-2 py-2.5 text-[12px] text-sky-50 disabled:opacity-40"
              >
                <Coffee size={12} /> Rest
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border/40 px-4 py-2.5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-white/15 px-3 py-1.5 text-[12px] text-muted-foreground hover:bg-white/5"
          >
            Close
          </button>
          {!sessionActive ? (
            <button
              type="button"
              disabled={busy || !canStart}
              onClick={() => {
                onStart();
                onClose();
              }}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600/85 px-3 py-1.5 text-[12px] disabled:opacity-40"
            >
              <Play size={12} /> Start focus
            </button>
          ) : null}
        </div>
      </div>
    </div>,
    document.body,
  );
}

function sessionDurationSec(s: ActualSession): number {
  const a = s.start_time ? Date.parse(s.start_time) : NaN;
  const b = s.end_time ? Date.parse(s.end_time) : Date.now();
  if (!Number.isFinite(a) || !Number.isFinite(b) || b <= a) return 0;
  return Math.min(8 * 3600, (b - a) / 1000);
}

function resolveSite(s: ActualSession): string {
  const fromField = normalizeSite(String(s.site || ""));
  if (fromField) return fromField;
  // Prefer embedded host in app_name (msedge:youtube.com) before title scrape.
  const fromApp = normalizeSite(String(s.app_name || ""));
  if (fromApp) return fromApp;
  if (looksLikeDomain(s.app_name)) {
    const again = normalizeSite(String(s.app_name || "").replace(/^[^:]+:/, ""));
    if (again) return again;
  }
  const exe = normalizeExe(String(s.app_name || ""));
  if (exe && BROWSERS.has(exe)) return siteFromTitle(s.window_title);
  if (
    s.source === "extension" ||
    s.source === "track_tab" ||
    s.source === "browser" ||
    s.source === "selftracker"
  ) {
    return siteFromTitle(s.window_title);
  }
  return siteFromTitle(s.window_title);
}

function rankUsage(sessions: ActualSession[]): {
  apps: Map<string, number>;
  sites: Map<string, number>;
} {
  const apps = new Map<string, number>();
  const sites = new Map<string, number>();
  for (const s of sessions) {
    if (s.source === "wearable_sleep" || String(s.category || "").toLowerCase() === "sleep") continue;
    const sec = sessionDurationSec(s);
    if (sec < 1) continue;
    const site = resolveSite(s);
    if (site) {
      sites.set(site, (sites.get(site) || 0) + sec);
      continue;
    }
    const exe = normalizeExe(String(s.app_name || ""));
    if (!exe || PROTECTED.has(exe) || BROWSERS.has(exe)) continue;
    apps.set(exe, (apps.get(exe) || 0) + sec);
  }
  return { apps, sites };
}

/** Instant Home ranking from day_activities.json — no enforcer pipe. */
async function rankUsageFromDayActivitiesMirror(): Promise<{
  apps: Map<string, number>;
  sites: Map<string, number>;
}> {
  const apps = new Map<string, number>();
  const sites = new Map<string, number>();
  if (!isFocusDesktopShell()) return { apps, sites };
  try {
    const res = await fetch(focusDataUrl("day_activities.json"), { cache: "no-store" });
    if (!res.ok) return { apps, sites };
    const j = (await res.json()) as {
      activities?: Array<{ key?: string; label?: string; seconds?: number }>;
    };
    for (const a of j.activities || []) {
      const sec = typeof a.seconds === "number" && Number.isFinite(a.seconds) ? a.seconds : 0;
      if (sec < 1) continue;
      const label = String(a.label || a.key || "");
      const key = String(a.key || label);
      const site =
        normalizeSite(label) ||
        normalizeSite(key.replace(/^app:/i, "")) ||
        normalizeSite(label.replace(/^[^:]+:/, ""));
      if (site) {
        sites.set(site, (sites.get(site) || 0) + sec);
        continue;
      }
      const exe = normalizeExe(label.replace(/^app:/i, "")) || normalizeExe(key.replace(/^app:/i, ""));
      if (!exe || PROTECTED.has(exe) || BROWSERS.has(exe)) continue;
      apps.set(exe, (apps.get(exe) || 0) + sec);
    }
  } catch {
    /* mirror missing */
  }
  return { apps, sites };
}

function setDragPayload(dt: DataTransfer, kind: ChipKind, id: string, from: Zone) {
  const json = JSON.stringify({ kind, id, from });
  dt.setData(MIME, json);
  dt.setData("text/plain", json);
  dt.effectAllowed = "move";
}

function readDragPayload(dt: DataTransfer): { kind: ChipKind; id: string; from: Zone } | null {
  const raw = dt.getData(MIME) || dt.getData("text/plain");
  if (!raw) return null;
  try {
    const o = JSON.parse(raw) as { kind?: string; id?: string; exe?: string; from?: Zone };
    const kind: ChipKind = o.kind === "site" ? "site" : "app";
    const id =
      kind === "site"
        ? normalizeSite(String(o.id || o.exe || ""))
        : normalizeExe(String(o.id || o.exe || ""));
    if (!id) return null;
    const from = o.from === "allow" || o.from === "block" || o.from === "pool" ? o.from : "pool";
    return { kind, id, from };
  } catch {
    return null;
  }
}

function Chip({
  chip,
  zone,
  locked,
  onRemove,
}: {
  chip: UsageChip;
  zone: Zone;
  locked: boolean;
  onRemove?: () => void;
}) {
  const isSite = chip.kind === "site";
  return (
    <button
      type="button"
      draggable={!locked}
      onDragStart={(e) => {
        if (locked) {
          e.preventDefault();
          return;
        }
        setDragPayload(e.dataTransfer, chip.kind, chip.id, zone);
      }}
      onClick={() => {
        if (!locked && onRemove) onRemove();
      }}
      title={
        locked
          ? chip.id
          : `${chip.id}${chip.seconds > 0 ? ` · ${formatHoursMinsFromSeconds(chip.seconds)}` : ""}${
              onRemove ? " — drag or click to unassign" : " — drag to Allow or Block"
            }`
      }
      className={cn(
        "group inline-flex max-w-full items-center gap-1 rounded-lg border px-2 py-1 text-[11px] transition-colors",
        zone === "allow" &&
          (isSite
            ? "border-amber-400/35 bg-amber-500/12 text-amber-50"
            : "border-emerald-400/35 bg-emerald-500/12 text-emerald-50"),
        zone === "block" && "border-rose-400/35 bg-rose-500/12 text-rose-50",
        zone === "pool" &&
          (isSite
            ? "border-amber-400/25 bg-amber-500/[0.07] text-amber-50/95 hover:bg-amber-500/12"
            : "border-white/15 bg-white/[0.04] text-foreground/90 hover:bg-white/[0.07]"),
        locked ? "cursor-default opacity-70" : "cursor-grab active:cursor-grabbing",
      )}
    >
      {!locked ? (
        <GripVertical className="size-3 shrink-0 opacity-40 group-hover:opacity-70" aria-hidden />
      ) : null}
      {isSite ? <Globe className="size-3 shrink-0 opacity-60" aria-hidden /> : null}
      <span className="truncate font-medium">{chip.label}</span>
      {chip.seconds > 0 ? (
        <span className="shrink-0 tabular-nums text-[10px] opacity-60">
          {formatHoursMinsFromSeconds(chip.seconds)}
        </span>
      ) : null}
    </button>
  );
}

function DropColumn({
  title,
  hint,
  zone,
  chips,
  locked,
  accent,
  icon,
  onDropChip,
  onRemove,
  footer,
}: {
  title: string;
  hint: string;
  zone: "allow" | "block";
  chips: UsageChip[];
  locked: boolean;
  accent: string;
  icon: ReactNode;
  onDropChip: (kind: ChipKind, id: string, from: Zone) => void;
  onRemove: (kind: ChipKind, id: string) => void;
  footer?: ReactNode;
}) {
  const [over, setOver] = useState(false);

  return (
    <div
      onDragOver={(e) => {
        if (locked) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        if (locked) return;
        e.preventDefault();
        setOver(false);
        const payload = readDragPayload(e.dataTransfer);
        if (!payload || payload.from === zone) return;
        onDropChip(payload.kind, payload.id, payload.from);
      }}
      className={cn(
        "min-h-[5.5rem] rounded-xl border px-2.5 py-2 transition-colors",
        accent,
        over && !locked && "ring-1 ring-sky-400/40 bg-sky-500/10",
        locked && "opacity-70",
      )}
    >
      <div className="mb-1.5 flex items-center gap-1.5">
        {icon}
        <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{title}</p>
      </div>
      <div className="flex min-h-[2.25rem] flex-wrap gap-1.5">
        {chips.length === 0 ? (
          <span className="text-[11px] text-muted-foreground/80">{hint}</span>
        ) : (
          chips.map((c) => (
            <Chip
              key={`${c.kind}:${c.id}`}
              chip={c}
              zone={zone}
              locked={locked}
              onRemove={() => onRemove(c.kind, c.id)}
            />
          ))
        )}
      </div>
      {footer}
    </div>
  );
}

/** Unified Home work-session + Allow/Block + most-used strip. */
export function HomeAllowBlockRail() {
  const freeDay = useFreeDay();
  const [catalog, setCatalog] = useState<UsageChip[]>(() => productivitySeedChips());
  const [allowApps, setAllowApps] = useState<string[]>([]);
  const [allowSites, setAllowSites] = useState<string[]>([]);
  const [block, setBlock] = useState<string[]>([]);
  const [sessionActive, setSessionActive] = useState(false);
  const [endsAt, setEndsAt] = useState("");
  const [minutes, setMinutes] = useState(50);
  const [restMinutes, setRestMinutes] = useState(10);
  const [timerOpen, setTimerOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usageLoaded, setUsageLoaded] = useState(false);
  const [listsLoaded, setListsLoaded] = useState(false);
  /** True once overlay returned at least one ranked app/site (seconds > 0). */
  const [hasUsageRank, setHasUsageRank] = useState(false);
  const [poolOver, setPoolOver] = useState(false);
  const [appDraft, setAppDraft] = useState("");
  const [siteDraft, setSiteDraft] = useState("");
  const allowAppsRef = useRef(allowApps);
  const allowSitesRef = useRef(allowSites);
  const blockRef = useRef(block);
  const catalogRef = useRef(catalog);
  allowAppsRef.current = allowApps;
  allowSitesRef.current = allowSites;
  blockRef.current = block;
  catalogRef.current = catalog;

  // Allow + Start work any day (session-first). Block→Arm still needs free day / pass.
  const locked = sessionActive || busy;
  const armLocked = sessionActive || !freeDay || busy;

  const ensureCatalog = useCallback((chips: UsageChip[]) => {
    setCatalog((cur) => {
      const byKey = new Map(cur.map((c) => [`${c.kind}:${c.id}`, c]));
      for (const chip of chips) {
        const key = `${chip.kind}:${chip.id}`;
        const prev = byKey.get(key);
        byKey.set(key, {
          ...chip,
          label: chip.label || prev?.label || (chip.kind === "app" ? labelForExe(chip.id) : chip.id),
          seconds: Math.max(chip.seconds, prev?.seconds ?? 0),
        });
      }
      return [...byKey.values()].sort(
        (a, b) => b.seconds - a.seconds || a.label.localeCompare(b.label),
      );
    });
  }, []);

  const loadLists = useCallback(async () => {
    try {
      const [sessionRes, policyRes] = await Promise.all([
        fetch(focusDataUrl("work_session.json"), { cache: "no-store" }).catch(() => null),
        fetch(focusDataUrl("enforcer_policy.json"), { cache: "no-store" }).catch(() => null),
      ]);
      if (sessionRes && sessionRes.ok) {
        const doc = (await sessionRes.json()) as SessionDoc;
        setSessionActive(Boolean(doc.active));
        setEndsAt(doc.ends_at || "");
        const apps = Array.isArray(doc.apps) ? doc.apps.map(normalizeExe).filter(Boolean) : [];
        const sites = Array.isArray(doc.sites)
          ? doc.sites.map((x) => normalizeSite(String(x))).filter(Boolean)
          : [];
        setAllowApps(apps);
        setAllowSites(sites);
        ensureCatalog([
          ...apps.map((id) => ({ kind: "app" as const, id, label: labelForExe(id), seconds: 0 })),
          ...sites.map((id) => ({ kind: "site" as const, id, label: id, seconds: 0 })),
        ]);
      }
      if (policyRes && policyRes.ok) {
        const pol = (await policyRes.json()) as { exes?: unknown; hard_block_armed?: boolean };
        const exes = Array.isArray(pol.exes)
          ? pol.exes.map((x) => normalizeExe(String(x || ""))).filter(Boolean)
          : [];
        setBlock(exes);
        setArmed(Boolean(pol.hard_block_armed));
        ensureCatalog(exes.map((id) => ({ kind: "app", id, label: labelForExe(id), seconds: 0 })));
      }
      setError(null);
      setListsLoaded(true);
    } catch (e: unknown) {
      if (!listsLoaded) setError(e instanceof Error ? e.message : "Couldn't load Allow / Block");
    }
  }, [ensureCatalog, listsLoaded]);

  const loadUsage = useCallback(async () => {
    const withTimeout = async <T,>(p: Promise<T>, ms: number, fallback: T): Promise<T> => {
      let timer: number | undefined;
      try {
        return await Promise.race([
          p,
          new Promise<T>((resolve) => {
            timer = window.setTimeout(() => resolve(fallback), ms);
          }),
        ]);
      } finally {
        if (timer != null) window.clearTimeout(timer);
      }
    };

    try {
      // Mirror first — pipe overlay can hang / truncate; day_activities already
      // ranks youtube.com etc. without blocking Home paint.
      let ranked = await rankUsageFromDayActivitiesMirror();
      if (ranked.apps.size === 0 && ranked.sites.size === 0) {
        const todayFrom = startOfDay(new Date());
        const todayTo = endOfDay(new Date());
        let sessions = await withTimeout(fetchActualOverlay(todayFrom, todayTo), 4500, []);
        ranked = rankUsage(sessions);
        if (ranked.apps.size === 0 && ranked.sites.size === 0) {
          sessions = await withTimeout(
            fetchActualOverlay(startOfDay(subDays(new Date(), 6)), todayTo),
            4500,
            [],
          );
          ranked = rankUsage(sessions);
        }
      }

      const appChips: UsageChip[] = [...ranked.apps.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 14)
        .map(([id, seconds]) => ({
          kind: "app" as const,
          id,
          label: labelForExe(id),
          seconds,
        }));
      const siteChips: UsageChip[] = [...ranked.sites.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(([id, seconds]) => ({
          kind: "site" as const,
          id,
          label: id,
          seconds,
        }));

      const realRank = appChips.length > 0 || siteChips.length > 0;
      setHasUsageRank(realRank);

      // Usage-ranked chips first. Productivity seeds only fill when usage is thin.
      const seeds = productivitySeedChips();
      const merged =
        appChips.length + siteChips.length >= 6
          ? [...appChips, ...siteChips]
          : [...appChips, ...siteChips, ...seeds];
      setCatalog((cur) => {
        const byKey = new Map<string, UsageChip>();
        for (const c of cur) {
          if (
            allowAppsRef.current.includes(c.id) ||
            allowSitesRef.current.includes(c.id) ||
            blockRef.current.includes(c.id)
          ) {
            byKey.set(`${c.kind}:${c.id}`, c);
          }
        }
        for (const chip of merged) {
          const key = `${chip.kind}:${chip.id}`;
          const prev = byKey.get(key);
          byKey.set(key, {
            ...chip,
            label: chip.label || prev?.label || chip.id,
            seconds: Math.max(chip.seconds, prev?.seconds ?? 0),
          });
        }
        return [...byKey.values()].sort(
          (a, b) => b.seconds - a.seconds || a.label.localeCompare(b.label),
        );
      });
    } catch {
      setHasUsageRank(false);
      setCatalog((cur) => {
        const byKey = new Map(cur.map((c) => [`${c.kind}:${c.id}`, c]));
        for (const chip of productivitySeedChips()) {
          const key = `${chip.kind}:${chip.id}`;
          if (!byKey.has(key)) byKey.set(key, chip);
        }
        return [...byKey.values()].sort(
          (a, b) => b.seconds - a.seconds || a.label.localeCompare(b.label),
        );
      });
    } finally {
      setUsageLoaded(true);
    }
  }, []);

  useEffect(() => {
    // Paint productivity starters immediately so Most used isn't empty while overlay loads.
    setCatalog((cur) => {
      if (cur.length) return cur;
      return productivitySeedChips();
    });
    void loadLists();
    void loadUsage();
    const id = window.setInterval(() => {
      void loadLists();
    }, 8000);
    return () => window.clearInterval(id);
  }, [loadLists, loadUsage]);

  // Soft nudge when focus is nearly up — opens timer so they can extend or rest.
  const nudgedRef = useRef<string>("");
  useEffect(() => {
    if (!sessionActive || !endsAt) return;
    const id = window.setInterval(() => {
      const left = remainingMs(endsAt);
      if (left == null || left <= 0 || left > NEAR_END_SEC * 1000) return;
      if (nudgedRef.current === endsAt) return;
      nudgedRef.current = endsAt;
      setTimerOpen(true);
    }, 5000);
    return () => window.clearInterval(id);
  }, [sessionActive, endsAt]);

  const chipFor = useCallback((kind: ChipKind, id: string): UsageChip => {
    const hit = catalogRef.current.find((c) => c.kind === kind && c.id === id);
    return (
      hit || {
        kind,
        id,
        label: kind === "app" ? labelForExe(id) : id,
        seconds: 0,
      }
    );
  }, []);

  const pool = useMemo(() => {
    const takenApps = new Set([...allowApps, ...block]);
    const takenSites = new Set(allowSites);
    return catalog
      .filter((c) => (c.kind === "app" ? !takenApps.has(c.id) : !takenSites.has(c.id)))
      .slice(0, 24);
  }, [catalog, allowApps, allowSites, block]);

  const allowChips = useMemo(
    () => [
      ...allowApps.map((id) => chipFor("app", id)),
      ...allowSites.map((id) => chipFor("site", id)),
    ],
    [allowApps, allowSites, chipFor, catalog],
  );
  const blockChips = useMemo(() => block.map((id) => chipFor("app", id)), [block, chipFor, catalog]);

  const persistSession = useCallback(
    async (nextApps: string[], nextSites: string[], nextActive: boolean, nextMinutes: number) => {
      setBusy(true);
      setError(null);
      try {
        if (isFocusDesktopShell() && isFocusEnforcerBridgeAvailable()) {
          const { enforcerNativeCmd } = await import("../../lib/enforcerNativeCmd");
          const native = await enforcerNativeCmd("session.set", {
            active: nextActive,
            minutes: nextActive ? nextMinutes : 0,
            apps: nextApps,
            sites: nextSites,
          });
          if (!native || native.ok === false) {
            throw new Error(String(native?.error || "enforcer_cmd_failed"));
          }
          const echoed = native.work_session as SessionDoc | undefined;
          if (echoed && typeof echoed === "object") {
            setAllowApps(
              Array.isArray(echoed.apps) ? echoed.apps.map(normalizeExe).filter(Boolean) : nextApps,
            );
            setAllowSites(
              Array.isArray(echoed.sites)
                ? echoed.sites.map((x) => normalizeSite(String(x))).filter(Boolean)
                : nextSites,
            );
            setSessionActive(Boolean(echoed.active));
            setEndsAt(echoed.ends_at || "");
          } else {
            setAllowApps(nextApps);
            setAllowSites(nextSites);
            setSessionActive(nextActive);
          }
        } else {
          setAllowApps(nextApps);
          setAllowSites(nextSites);
          setSessionActive(nextActive);
        }
        window.dispatchEvent(new CustomEvent(WORK_SESSION_UPDATED_EVENT));
      } catch (e: unknown) {
        setError(explain(e instanceof Error ? e.message : "Couldn't save session"));
        await loadLists();
      } finally {
        setBusy(false);
      }
    },
    [loadLists],
  );

  const persistBlock = useCallback(
    async (nextExes: string[]) => {
      if (!freeDay || sessionActive) {
        setError("Block · Arm needs a free day or day pass (Allow · session does not).");
        return;
      }
      setBusy(true);
      setError(null);
      try {
        if (isFocusDesktopShell() && isFocusEnforcerBridgeAvailable()) {
          await putEnforcerPolicy({
            hard_block_armed: armed,
            gate_locked: false,
            exes: nextExes,
          });
        }
        setBlock(nextExes);
      } catch (e: unknown) {
        setError(explain(e instanceof Error ? e.message : "Couldn't save Block"));
        await loadLists();
      } finally {
        setBusy(false);
      }
    },
    [freeDay, sessionActive, armed, loadLists],
  );

  const suggestLists = useCallback(async () => {
    if (locked || sessionActive) return;
    setBusy(true);
    setError(null);
    try {
      const chips = (catalog.length ? catalog : pool).slice(0, 40);
      const r = await suggestSessionLists(
        chips.map((c) => ({ kind: c.kind, id: c.id, label: c.label, seconds: c.seconds })),
      );
      const nextApps = r.allow_apps.map(normalizeExe).filter(Boolean);
      const nextSites = r.allow_sites.map(normalizeSite).filter(Boolean);
      const nextBlock = r.block_apps.map(normalizeExe).filter(Boolean);
      // Avoid putting the same exe in both allow and block — block wins.
      const blockSet = new Set(nextBlock);
      const allowAppsOnly = nextApps.filter((a) => !blockSet.has(a));
      setAllowApps(allowAppsOnly);
      setAllowSites(nextSites);
      if (freeDay) {
        await persistBlock(nextBlock);
      } else if (nextBlock.length) {
        setError("Suggest filled Allow. Block · Arm skipped — needs a free day or day pass.");
      }
      if (r.error) {
        setError(
          r.source === "heuristic"
            ? `Suggest used heuristics (${r.error})`
            : `Suggest partial: ${r.error}`,
        );
      }
    } catch (e: unknown) {
      setError(explain(e instanceof Error ? e.message : "Suggest failed"));
    } finally {
      setBusy(false);
    }
  }, [locked, freeDay, sessionActive, catalog, pool, persistBlock]);

  const moveTo = useCallback(
    (kind: ChipKind, idRaw: string, to: Zone) => {
      if (to === "block") {
        if (armLocked) return;
      } else if (locked) {
        return;
      }

      if (kind === "site") {
        const site = normalizeSite(idRaw);
        if (!site) {
          setError(explain("bad_site"));
          return;
        }
        if (to === "block") {
          setError(explain("site_not_blockable"));
          return;
        }
        ensureCatalog([{ kind: "site", id: site, label: site, seconds: 0 }]);
        const nextSites =
          to === "allow"
            ? allowSitesRef.current.includes(site)
              ? allowSitesRef.current
              : [...allowSitesRef.current, site]
            : allowSitesRef.current.filter((x) => x !== site);
        if (
          nextSites.length === allowSitesRef.current.length &&
          nextSites.every((x, i) => x === allowSitesRef.current[i])
        ) {
          return;
        }
        setAllowSites(nextSites);
        void persistSession(allowAppsRef.current, nextSites, false, 0);
        return;
      }

      const exe = normalizeExe(idRaw);
      if (!exe || PROTECTED.has(exe)) {
        setError(explain("protected_exe"));
        return;
      }
      if (BROWSERS.has(exe) && to === "allow") {
        setError(explain("browser_exe"));
        return;
      }
      ensureCatalog([{ kind: "app", id: exe, label: labelForExe(exe), seconds: 0 }]);

      const nextAllow = allowAppsRef.current.filter((x) => x !== exe);
      const nextBlock = blockRef.current.filter((x) => x !== exe);
      if (to === "allow") nextAllow.push(exe);
      if (to === "block") nextBlock.push(exe);

      const allowChanged =
        nextAllow.length !== allowAppsRef.current.length ||
        nextAllow.some((x, i) => x !== allowAppsRef.current[i]);
      const blockChanged =
        nextBlock.length !== blockRef.current.length ||
        nextBlock.some((x, i) => x !== blockRef.current[i]);

      if (allowChanged) setAllowApps(nextAllow);
      if (blockChanged) setBlock(nextBlock);

      if (allowChanged) void persistSession(nextAllow, allowSitesRef.current, false, 0);
      if (blockChanged) void persistBlock(nextBlock);
    },
    [locked, armLocked, ensureCatalog, persistSession, persistBlock],
  );

  const addApp = (raw: string) => {
    if (locked) return;
    const name = normalizeExe(raw);
    if (!name) {
      setError(explain("bad_exe"));
      return;
    }
    moveTo("app", name, "allow");
    setAppDraft("");
  };

  const addSite = (raw: string) => {
    if (locked) return;
    const host = normalizeSite(raw);
    if (!host) {
      setError(explain("bad_site"));
      return;
    }
    moveTo("site", host, "allow");
    setSiteDraft("");
  };

  const addToPool = (raw: string) => {
    if (locked) return;
    const t = raw.trim();
    if (!t) return;
    const asSite = t.includes(".") && !t.toLowerCase().endsWith(".exe");
    if (asSite) {
      const host = normalizeSite(t);
      if (!host) {
        setError(explain("bad_site"));
        return;
      }
      ensureCatalog([{ kind: "site", id: host, label: host, seconds: 0 }]);
    } else {
      const name = normalizeExe(t);
      if (!name || PROTECTED.has(name)) {
        setError(explain(name ? "protected_exe" : "bad_exe"));
        return;
      }
      ensureCatalog([{ kind: "app", id: name, label: labelForExe(name), seconds: 0 }]);
    }
    setAddOpen(false);
    setAppDraft("");
    setSiteDraft("");
  };

  const startOrEnd = async (nextActive: boolean) => {
    if (nextActive && allowApps.length === 0 && allowSites.length === 0) {
      setError(explain("empty_session"));
      return;
    }
    await persistSession(allowApps, allowSites, nextActive, minutes);
  };

  const extendSession = async (extraMin: number) => {
    if (!sessionActive || extraMin <= 0) return;
    const left = remainingMs(endsAt);
    const base =
      left != null && left > 0 ? Math.ceil(left / 60_000) : minutes > 0 ? minutes : 25;
    await persistSession(allowApps, allowSites, true, Math.min(720, base + extraMin));
  };

  const takeRest = async () => {
    // End focus so SoftLand/free rhythm can breathe; rest length is advisory in the dialog.
    await persistSession(allowApps, allowSites, false, 0);
    setTimerOpen(false);
    if (restMinutes > 0) {
      setError(null);
    }
  };

  return (
    <section className="gloss-panel overflow-hidden rounded-2xl border border-border/40">
      <div className="flex flex-wrap items-center gap-2 px-3.5 pt-2.5 pb-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <p className="text-[13px] font-medium text-foreground/90">Work session</p>
            {sessionActive ? (
              <span className="rounded-full border border-emerald-400/35 bg-emerald-500/15 px-2 py-0.5 text-[10px] text-emerald-100">
                Live · {endsLabel(endsAt)}
              </span>
            ) : (
              <span className="truncate text-[11px] text-muted-foreground">
                {summaryLine(allowApps, allowSites, minutes)}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            {sessionActive
              ? "Only Allow stays open while this runs. SoftLand ≠ Arm."
              : freeDay
                ? "Most used → Allow (session) or Block (Arm). Duration + Start when ready."
                : "Allow + Start anytime. Block · Arm needs a free day or day pass."}
          </p>
        </div>

          <button
            type="button"
            disabled={busy}
            onClick={() => setTimerOpen(true)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] tabular-nums disabled:opacity-40",
              sessionActive
                ? "border-amber-400/35 bg-amber-500/10 text-amber-50"
                : "border-emerald-400/40 bg-emerald-500/10 text-emerald-100 hover:bg-emerald-500/15",
            )}
            title="Open focus timer"
          >
            <Clock3 size={12} aria-hidden />
            {sessionActive ? "Timer" : minutes > 0 ? `${minutes}m` : "Open"}
          </button>

        {!sessionActive ? (
          <div className="inline-flex items-center gap-1.5">
            <button
              type="button"
              disabled={busy || locked || catalog.length === 0}
              onClick={() => void suggestLists()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-violet-400/35 bg-violet-500/10 px-2.5 py-1 text-[11px] text-violet-100 hover:bg-violet-500/15 disabled:opacity-40"
              title="Ask LLM host / OpenRouter (or heuristics) to fill Allow / Block"
            >
              <Sparkles size={11} /> {busy ? "…" : "Suggest"}
            </button>
          </div>
        ) : null}

        {sessionActive ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void startOrEnd(false)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-rose-400/40 bg-rose-500/15 px-2.5 py-1 text-[11px] text-rose-100 disabled:opacity-50"
          >
            <Square size={11} /> {busy ? "Ending…" : "End"}
          </button>
        ) : (
          <button
            type="button"
            disabled={busy || (allowApps.length === 0 && allowSites.length === 0)}
            onClick={() => void startOrEnd(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600/80 px-2.5 py-1 text-[11px] disabled:opacity-40"
          >
            <Play size={11} /> {busy ? "…" : "Start"}
          </button>
        )}
      </div>

      <div
        className={cn(
          "mx-3 mb-2 rounded-xl border border-dashed border-white/10 bg-black/20 px-2 py-2 transition-colors",
          poolOver && !locked && "border-sky-400/40 bg-sky-500/10",
        )}
        onDragOver={(e) => {
          if (locked) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
          setPoolOver(true);
        }}
        onDragLeave={() => setPoolOver(false)}
        onDrop={(e) => {
          if (locked) return;
          e.preventDefault();
          setPoolOver(false);
          const payload = readDragPayload(e.dataTransfer);
          if (!payload || payload.from === "pool") return;
          moveTo(payload.kind, payload.id, "pool");
        }}
      >
        <p className="mb-1.5 text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
          Most used
        </p>
        {!usageLoaded && pool.length === 0 ? (
          <p className="text-[11px] text-muted-foreground">Loading usage…</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {pool.map((c) => (
              <Chip key={`${c.kind}:${c.id}`} chip={c} zone="pool" locked={locked} />
            ))}
            {!sessionActive ? (
              addOpen ? (
                <div className="inline-flex min-w-[12rem] flex-1 items-center gap-1">
                  <input
                    autoFocus
                    value={appDraft}
                    disabled={locked}
                    onChange={(e) => setAppDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addToPool(appDraft);
                      }
                      if (e.key === "Escape") setAddOpen(false);
                    }}
                    placeholder="cursor.exe or github.com"
                    className="min-w-0 flex-1 rounded-lg border border-white/15 bg-black/35 px-2 py-1 text-[11px] disabled:opacity-40"
                  />
                  <button
                    type="button"
                    disabled={locked || !appDraft.trim()}
                    onClick={() => addToPool(appDraft)}
                    className="rounded-lg border border-white/15 px-2 py-1 text-[10px] disabled:opacity-40"
                  >
                    Add
                  </button>
                  <button
                    type="button"
                    onClick={() => setAddOpen(false)}
                    className="rounded-lg p-1 text-muted-foreground hover:bg-white/5"
                    aria-label="Cancel add"
                  >
                    <X size={12} />
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  disabled={locked}
                  onClick={() => setAddOpen(true)}
                  className="inline-flex items-center gap-0.5 rounded-lg border border-dashed border-white/20 px-2 py-1 text-[11px] text-muted-foreground hover:border-white/35 hover:text-foreground disabled:opacity-40"
                  title={
                    locked
                      ? "Add on a free day or day pass"
                      : "Add a program or website to Most used"
                  }
                >
                  <Plus size={12} /> Add
                </button>
              )
            ) : null}
            {pool.length === 0 && !addOpen ? (
              <span className="text-[11px] text-muted-foreground">
                {hasUsageRank
                  ? "All ranked items are assigned — drop here to unassign."
                  : "No usage yet — tap + to add a program or site."}
              </span>
            ) : null}
          </div>
        )}
      </div>

      <div className="grid gap-2 px-3 pb-3 sm:grid-cols-2">
        <DropColumn
          title="Allow · session"
          hint="Drop work apps or sites"
          zone="allow"
          chips={allowChips}
          locked={locked}
          accent="border-emerald-400/20 bg-emerald-500/[0.06]"
          icon={<ShieldCheck className="size-3 text-emerald-300/90" aria-hidden />}
          onDropChip={(kind, id) => moveTo(kind, id, "allow")}
          onRemove={(kind, id) => moveTo(kind, id, "pool")}
        />
        <DropColumn
          title="Block · Arm"
          hint={freeDay ? "Drop Arm kill-list apps" : "Needs free day / day pass"}
          zone="block"
          chips={blockChips}
          locked={armLocked}
          accent="border-rose-400/20 bg-rose-500/[0.06]"
          icon={<Ban className="size-3 text-rose-300/90" aria-hidden />}
          onDropChip={(kind, id) => moveTo(kind, id, "block")}
          onRemove={(kind, id) => moveTo(kind, id, "pool")}
        />
      </div>

      {error ? (
        <p className="border-t border-border/30 px-3.5 py-2 text-xs text-rose-300">{error}</p>
      ) : null}

      <SessionTimerDialog
        open={timerOpen}
        onClose={() => setTimerOpen(false)}
        freeDay={freeDay}
        sessionActive={sessionActive}
        minutes={minutes}
        endsAt={endsAt}
        restMinutes={restMinutes}
        onChangeMinutes={setMinutes}
        onChangeRest={setRestMinutes}
        onExtend={(n) => void extendSession(n)}
        onTakeRest={() => void takeRest()}
        onStart={() => void startOrEnd(true)}
        canStart={allowApps.length > 0 || allowSites.length > 0}
        busy={busy}
      />
    </section>
  );
}

export default HomeAllowBlockRail;
