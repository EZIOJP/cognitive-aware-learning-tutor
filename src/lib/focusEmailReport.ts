/**
 * Focus daily email report — compose from mirrors, open mailto.
 * Fixed recipient; no WhatsApp / Cloud API / Study :8000.
 */

import { focusDataUrl } from "../utils/focusDataUrl";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";
import type { ActivitiesResponse } from "../api/behaviorClient";
import type { DayRollupMirror } from "../api/focusMirrors";

const LS_KEY = "calt:focus-email-report:v1";
const SENT_FLAG = "calt:email-report-sent:";

/** Hard-coded daily report inbox (product choice). */
export const FOCUS_REPORT_EMAIL = "JPMASTILA12@gmail.com";

export type FocusEmailReportPrefs = {
  enabled: boolean;
  /** Local HH:mm for once-per-day send while Focus is open. */
  sendTime: string;
  includeActivities: boolean;
  includeTodos: boolean;
};

export const DEFAULT_EMAIL_REPORT: FocusEmailReportPrefs = {
  enabled: true,
  sendTime: "21:00",
  includeActivities: true,
  includeTodos: true,
};

export const FOCUS_EMAIL_REPORT_EVENT = "calt:focus-email-report-updated";

export function loadEmailReportPrefs(): FocusEmailReportPrefs {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { ...DEFAULT_EMAIL_REPORT };
    const p = JSON.parse(raw) as Partial<FocusEmailReportPrefs>;
    return {
      enabled: typeof p.enabled === "boolean" ? p.enabled : DEFAULT_EMAIL_REPORT.enabled,
      sendTime:
        typeof p.sendTime === "string" && /^\d{1,2}:\d{2}$/.test(p.sendTime)
          ? p.sendTime
          : DEFAULT_EMAIL_REPORT.sendTime,
      includeActivities:
        typeof p.includeActivities === "boolean"
          ? p.includeActivities
          : DEFAULT_EMAIL_REPORT.includeActivities,
      includeTodos:
        typeof p.includeTodos === "boolean"
          ? p.includeTodos
          : DEFAULT_EMAIL_REPORT.includeTodos,
    };
  } catch {
    return { ...DEFAULT_EMAIL_REPORT };
  }
}

export function saveEmailReportPrefs(prefs: FocusEmailReportPrefs): FocusEmailReportPrefs {
  const next: FocusEmailReportPrefs = {
    enabled: prefs.enabled,
    sendTime: prefs.sendTime,
    includeActivities: prefs.includeActivities,
    includeTodos: prefs.includeTodos,
  };
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(next));
    window.dispatchEvent(new CustomEvent(FOCUS_EMAIL_REPORT_EVENT, { detail: next }));
  } catch {
    /* ignore */
  }
  return next;
}

function localYmd(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function fmtMins(m: number): string {
  const h = Math.floor(m / 60);
  const mm = m % 60;
  if (h <= 0) return `${mm}m`;
  return `${h}h ${mm}m`;
}

export type DailyReportContext = {
  rollup: DayRollupMirror | null;
  activities: ActivitiesResponse | null;
  openTodos: string[];
  bibleDone?: boolean;
  planConfirmed?: boolean;
};

export async function loadDailyReportContext(): Promise<DailyReportContext> {
  const out: DailyReportContext = {
    rollup: null,
    activities: null,
    openTodos: [],
  };
  if (!isFocusDesktopShell()) return out;
  try {
    const [rollupRes, actRes, loopRes] = await Promise.all([
      fetch(focusDataUrl("day_rollup.json"), { cache: "no-store" }),
      fetch(focusDataUrl("day_activities.json"), { cache: "no-store" }),
      fetch(focusDataUrl("day_loop.json"), { cache: "no-store" }),
    ]);
    if (rollupRes.ok) out.rollup = (await rollupRes.json()) as DayRollupMirror;
    if (actRes.ok) out.activities = (await actRes.json()) as ActivitiesResponse;
    if (loopRes.ok) {
      const loop = (await loopRes.json()) as {
        bible_done?: boolean;
        plan_confirmed?: boolean;
        tasks?: { title?: string; done?: boolean }[];
      };
      out.bibleDone = Boolean(loop.bible_done);
      out.planConfirmed = Boolean(loop.plan_confirmed);
      out.openTodos = (loop.tasks || [])
        .filter((t) => !t.done && t.title)
        .map((t) => String(t.title))
        .slice(0, 6);
    }
  } catch {
    /* mirrors optional */
  }
  return out;
}

export function composeDailyEmailReport(
  ctx: DailyReportContext,
  prefs?: FocusEmailReportPrefs,
): string {
  const p = prefs || loadEmailReportPrefs();
  const day = ctx.rollup?.local_date || localYmd();
  const prodMin =
    typeof ctx.rollup?.productive_minutes === "number"
      ? ctx.rollup.productive_minutes
      : typeof ctx.rollup?.productive_seconds === "number"
        ? Math.floor(ctx.rollup.productive_seconds / 60)
        : 0;
  const totalMin =
    typeof ctx.rollup?.total_seconds === "number"
      ? Math.floor(ctx.rollup.total_seconds / 60)
      : prodMin;
  const goal =
    typeof ctx.rollup?.daily_focus_minutes === "number"
      ? ctx.rollup.daily_focus_minutes
      : 0;

  const lines: string[] = [];
  lines.push(`CALT Focus — daily report (${day})`);
  lines.push("");
  lines.push(`Productive: ${fmtMins(prodMin)}${goal > 0 ? ` / ${fmtMins(goal)} goal` : ""}`);
  lines.push(`Screen time: ${fmtMins(totalMin)}`);
  if (ctx.rollup?.goal_met) lines.push("Goal: met");
  else if (goal > 0) lines.push("Goal: not yet");
  if (ctx.bibleDone != null) lines.push(`Bible: ${ctx.bibleDone ? "done" : "open"}`);
  if (ctx.planConfirmed != null) lines.push(`Plan: ${ctx.planConfirmed ? "confirmed" : "open"}`);

  if (p.includeActivities && ctx.activities?.activities?.length) {
    lines.push("");
    lines.push("Top apps:");
    for (const a of ctx.activities.activities.slice(0, 8)) {
      const mins = Math.round((a.seconds || 0) / 60);
      if (mins <= 0) continue;
      lines.push(`• ${a.label} — ${fmtMins(mins)} (${a.category || "—"})`);
    }
  }

  if (p.includeTodos && ctx.openTodos.length) {
    lines.push("");
    lines.push("Open todos:");
    for (const t of ctx.openTodos) lines.push(`• ${t}`);
  }

  lines.push("");
  lines.push("— sent from CALT Focus");
  // mailto clients often truncate long bodies
  return lines.join("\n").slice(0, 1800);
}

export function emailReportSubject(ctx: DailyReportContext): string {
  const day = ctx.rollup?.local_date || localYmd();
  return `CALT Focus daily report — ${day}`;
}

export function mailtoReportUrl(to: string, subject: string, body: string): string {
  const q = new URLSearchParams();
  q.set("subject", subject);
  q.set("body", body);
  return `mailto:${encodeURIComponent(to)}?${q.toString()}`;
}

export function openExternalUrl(url: string): boolean {
  if (typeof window === "undefined") return false;
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void } };
  };
  if (w.chrome?.webview?.postMessage) {
    w.chrome.webview.postMessage({ type: "open_external", v: 1, url });
    return true;
  }
  try {
    window.open(url, "_blank", "noopener,noreferrer");
    return true;
  } catch {
    return false;
  }
}

/** Open default mail client to FOCUS_REPORT_EMAIL with the report. User taps Send. */
export async function sendEmailReportNow(
  prefs?: FocusEmailReportPrefs,
): Promise<{ ok: boolean; error?: string; preview: string; to: string }> {
  const p = prefs || loadEmailReportPrefs();
  const ctx = await loadDailyReportContext();
  const preview = composeDailyEmailReport(ctx, p);
  const subject = emailReportSubject(ctx);
  const url = mailtoReportUrl(FOCUS_REPORT_EMAIL, subject, preview);
  const opened = openExternalUrl(url);
  return {
    ok: opened,
    preview,
    to: FOCUS_REPORT_EMAIL,
    error: opened ? undefined : "mailto_failed",
  };
}

export function emailReportSentToday(): boolean {
  try {
    return localStorage.getItem(SENT_FLAG + localYmd()) === "1";
  } catch {
    return false;
  }
}

export function markEmailReportSentToday(): void {
  try {
    localStorage.setItem(SENT_FLAG + localYmd(), "1");
  } catch {
    /* ignore */
  }
}

export function shouldAutoSendEmailReport(prefs?: FocusEmailReportPrefs): boolean {
  const p = prefs || loadEmailReportPrefs();
  if (!p.enabled) return false;
  if (emailReportSentToday()) return false;
  const m = /^(\d{1,2}):(\d{2})$/.exec(p.sendTime.trim());
  if (!m) return false;
  const hh = Number(m[1]);
  const mm = Number(m[2]);
  if (!Number.isFinite(hh) || !Number.isFinite(mm)) return false;
  const now = new Date();
  const target = new Date(now);
  target.setHours(hh, mm, 0, 0);
  const delta = now.getTime() - target.getTime();
  return delta >= 0 && delta < 20 * 60_000;
}
