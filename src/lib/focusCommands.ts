/**
 * In-app Focus commands (Jarvis box).
 * Sensitive SoftLand/Arm changes keep server-side confirms — no bypass.
 */

import { focusDataUrl } from "../utils/focusDataUrl";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "./enforcerNativeCmd";
import {
  jarvisBrief,
  jarvisChat,
  jarvisSpeak,
  jarvisStop,
  loadFocusJarvisPrefs,
  saveFocusJarvisPrefs,
  type JarvisContext,
  type JarvisVoiceMode,
} from "./focusJarvis";
import {
  FOCUS_REPORT_EMAIL,
  loadEmailReportPrefs,
  markEmailReportSentToday,
  sendEmailReportNow,
} from "./focusEmailReport";

export type FocusCommandResult = {
  ok: boolean;
  reply: string;
  /** Spoken when Jarvis speak is on. */
  speak?: boolean;
  /** llm = free chat / brief from host; cmd = built-in; canned = offline fallback. */
  source?: "llm" | "cmd" | "canned";
};

export const FOCUS_COMMAND_HELP = [
  "help — this list",
  "status / summary — SoftLand, Arm, focus, bible/plan/todos",
  "brief — morning / day brief",
  "plan · todos — today's agenda / open tasks",
  "export [days] [json|csv] — write productivity_export.*",
  "report — email daily report (opens mail)",
  "speak on|off — Jarvis voice",
  "voice jarvis|normal — voice model",
  "model [name] — show or set OpenJarvis model",
  "serve | start — start OpenJarvis API (no GUI)",
  "load / unload [name] — VRAM warm / free",
  "classify — scan uncategorized apps",
  "stop — stop speaking",
  "session end — end work session",
  "softland on | softland off UNLOCK",
  "pass — day pass (bible required)",
  "winddown — SoftLand emergency wind-down",
  "close browsers | close app name.exe[,…]",
  "lock · sleep",
  "shutdown CONFIRM | shutdown 5m CONFIRM | shutdown cancel",
  "anything else — free chat via local OpenJarvis",
].join("\n");

function norm(line: string): string {
  return line.trim().replace(/^\//, "").replace(/\s+/g, " ");
}

async function fetchJson(name: string): Promise<Record<string, unknown> | null> {
  if (!isFocusDesktopShell()) return null;
  try {
    const r = await fetch(focusDataUrl(name), { cache: "no-store" });
    if (!r.ok) return null;
    return (await r.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

async function cmdStatus(): Promise<FocusCommandResult> {
  const [rollup, softland, enforcer, session] = await Promise.all([
    fetchJson("day_rollup.json"),
    fetchJson("softland_policy.json"),
    fetchJson("enforcer_status.json"),
    fetchJson("work_session.json"),
  ]);
  const prod =
    typeof rollup?.productive_minutes === "number"
      ? rollup.productive_minutes
      : typeof rollup?.productive_seconds === "number"
        ? Math.floor(Number(rollup.productive_seconds) / 60)
        : 0;
  const goal =
    typeof rollup?.daily_focus_minutes === "number" ? rollup.daily_focus_minutes : 0;
  const sl = Boolean(
    softland?.softland_enabled ?? (softland as { enabled?: boolean } | null)?.enabled,
  );
  const armed = Boolean(enforcer?.armed);
  const sessionActive = Boolean(session?.active);
  const parts = [
    `SoftLand ${sl ? "ON" : "OFF"}`,
    `Arm ${armed ? "ARMED" : "off"}`,
    `Focus ${prod}m${goal > 0 ? ` / ${goal}m` : ""}`,
    sessionActive ? "Work session live" : "No work session",
  ];
  return { ok: true, reply: parts.join(" · "), speak: true };
}

async function cmdBrief(): Promise<FocusCommandResult> {
  const rollup = await fetchJson("day_rollup.json");
  const loop = await fetchJson("day_loop.json");
  const softland = await fetchJson("softland_policy.json");
  const prod =
    typeof rollup?.productive_minutes === "number"
      ? Number(rollup.productive_minutes)
      : undefined;
  const goal =
    typeof rollup?.daily_focus_minutes === "number"
      ? Number(rollup.daily_focus_minutes)
      : undefined;
  const tasks = Array.isArray(loop?.tasks)
    ? (loop!.tasks as { title?: string; done?: boolean }[])
        .filter((t) => !t.done && t.title)
        .map((t) => String(t.title))
        .slice(0, 6)
    : [];
  const r = await jarvisBrief({
    productiveMinutes: prod,
    goalMinutes: goal,
    bibleDone: Boolean(loop?.bible_done),
    planConfirmed: Boolean(loop?.plan_confirmed),
    planningEnabled:
      typeof loop?.planning_enabled === "boolean" ? Boolean(loop.planning_enabled) : false,
    mode: softland?.softland_enabled ? "softland" : "off",
    openTodos: tasks,
  });
  if (!r.line) return { ok: false, reply: "Jarvis is off or brief empty." };
  return { ok: true, reply: r.line, speak: true };
}

async function cmdReport(): Promise<FocusCommandResult> {
  const prefs = loadEmailReportPrefs();
  const r = await sendEmailReportNow(prefs);
  if (!r.ok) return { ok: false, reply: r.error || "Could not open mail." };
  markEmailReportSentToday();
  return {
    ok: true,
    reply: `Opened email to ${FOCUS_REPORT_EMAIL}. Tap Send in your mail app.`,
    speak: true,
  };
}

async function cmdSessionEnd(): Promise<FocusCommandResult> {
  if (!isFocusEnforcerBridgeAvailable()) {
    return { ok: false, reply: "Enforcer bridge unavailable — open Focus desktop." };
  }
  const prev = await fetchJson("work_session.json");
  const apps = Array.isArray(prev?.apps) ? prev!.apps : [];
  const sites = Array.isArray(prev?.sites) ? prev!.sites : [];
  const res = await enforcerNativeCmd("session.set", {
    active: false,
    apps,
    sites,
  });
  if (!res || res.ok === false) {
    return { ok: false, reply: `Session end failed: ${res?.error || "no_bridge"}` };
  }
  return { ok: true, reply: "Work session ended.", speak: true };
}

async function cmdSoftland(on: boolean, confirm?: string): Promise<FocusCommandResult> {
  if (!isFocusEnforcerBridgeAvailable()) {
    return { ok: false, reply: "Enforcer bridge unavailable — open Focus desktop." };
  }
  const payload: Record<string, unknown> = { enabled: on };
  if (!on) {
    if ((confirm || "").toUpperCase() !== "UNLOCK") {
      return {
        ok: false,
        reply: 'To turn SoftLand off, type: softland off UNLOCK',
      };
    }
    payload.confirm = "UNLOCK";
  }
  const res = await enforcerNativeCmd("softland.set_enabled", payload);
  if (!res || res.ok === false) {
    const err = String(res?.error || "failed");
    if (err === "free_day_required") {
      return { ok: false, reply: "SoftLand toggle needs a free day or day pass." };
    }
    if (err === "confirm_required") {
      return { ok: false, reply: 'Confirm required — softland off UNLOCK' };
    }
    return { ok: false, reply: `SoftLand failed: ${err}` };
  }
  return { ok: true, reply: on ? "SoftLand on." : "SoftLand off.", speak: true };
}

async function cmdPass(): Promise<FocusCommandResult> {
  if (!isFocusEnforcerBridgeAvailable()) {
    return { ok: false, reply: "Enforcer bridge unavailable — open Focus desktop." };
  }
  const res = await enforcerNativeCmd("day.grant_pass", {});
  if (!res || res.ok === false) {
    const err = String(res?.error || "failed");
    if (err === "bible_required") {
      return { ok: false, reply: "Bible first — then day pass." };
    }
    return { ok: false, reply: `Day pass: ${err}` };
  }
  return { ok: true, reply: "Day pass granted.", speak: true };
}

/**
 * Parse and run one Focus command line.
 * Accepts with or without leading `/`.
 */
export async function runFocusCommand(raw: string): Promise<FocusCommandResult> {
  const line = norm(raw);
  if (!line) return { ok: false, reply: "Type a command — help for the list." };

  const lower = line.toLowerCase();
  const parts = lower.split(" ");
  const head = parts[0] || "";

  if (head === "help" || head === "?") {
    return { ok: true, reply: FOCUS_COMMAND_HELP, speak: false };
  }
  if (head === "brief" || head === "b") return cmdBrief();
  if (head === "status" || head === "st") return cmdStatus();
  if (head === "summary" || head === "sum" || head === "day") {
    const [loop, life] = await Promise.all([
      fetchJson("day_loop.json"),
      fetchJson("life_today.json"),
    ]);
    const st = await cmdStatus();
    const bible = Boolean(loop?.bible_done);
    const planOk = Boolean(loop?.plan_confirmed);
    const todos = Array.isArray(loop?.tasks)
      ? (loop!.tasks as { done?: boolean }[]).filter((t) => !t.done).length
      : 0;
    const steps = typeof life?.steps === "number" ? life.steps : 0;
    const sleep =
      typeof life?.sleep_hours === "number" ? Number(life.sleep_hours).toFixed(1) : null;
    const lines = [
      st.reply,
      `Bible ${bible ? "done" : "open"} · Plan ${planOk ? "confirmed" : "pending"} · Todos ${todos}`,
    ];
    if (steps || sleep) lines.push(`Life: sleep ${sleep ?? "—"}h · steps ${steps || "—"}`);
    lines.push("SoftLand ≠ Arm.");
    return { ok: true, reply: lines.join("\n"), speak: true, source: "cmd" };
  }
  if (head === "plan" || head === "agenda") {
    const blocks = await fetchJson("plan_blocks.json");
    const ymd = new Date();
    const day = `${ymd.getFullYear()}-${String(ymd.getMonth() + 1).padStart(2, "0")}-${String(ymd.getDate()).padStart(2, "0")}`;
    const list = Array.isArray(blocks?.blocks) ? (blocks!.blocks as { title?: string; start_at?: string }[]) : [];
    const today = list
      .filter((b) => String(b.start_at || "").includes(day) && b.title)
      .map((b) => String(b.title))
      .slice(0, 12);
    if (!today.length) return { ok: true, reply: `No plan blocks for ${day}.`, source: "cmd" };
    return {
      ok: true,
      reply: `Plan ${day}\n` + today.map((t, i) => `${i + 1}. ${t}`).join("\n"),
      speak: false,
      source: "cmd",
    };
  }
  if (head === "todos" || head === "todo" || head === "tasks") {
    const loop = await fetchJson("day_loop.json");
    const open = Array.isArray(loop?.tasks)
      ? (loop!.tasks as { title?: string; done?: boolean }[])
          .filter((t) => !t.done && t.title)
          .map((t) => String(t.title))
          .slice(0, 15)
      : [];
    if (!open.length) return { ok: true, reply: "No open todos.", source: "cmd" };
    return {
      ok: true,
      reply: `Todos (${open.length})\n` + open.map((t, i) => `${i + 1}. ${t}`).join("\n"),
      source: "cmd",
    };
  }
  if (head === "export") {
    if (!isFocusEnforcerBridgeAvailable()) {
      return { ok: false, reply: "Export needs Focus desktop." };
    }
    let days = 7;
    let format = "json";
    for (const p of parts.slice(1)) {
      if (p === "csv" || p === "json" || p === "csv_wide") format = p;
      else {
        const d = Number(p);
        if (Number.isFinite(d) && d > 0) days = Math.min(90, Math.floor(d));
      }
    }
    const res = await enforcerNativeCmd("productivity.export", { days, format, skip_empty: true }, 60000);
    if (!res || res.ok === false) {
      return { ok: false, reply: `Export failed: ${res?.error || "no_bridge"}`, source: "cmd" };
    }
    return {
      ok: true,
      reply: `Export OK (${days}d, ${format}) → data/productivity/behavior/productivity_export.*`,
      speak: true,
      source: "cmd",
    };
  }
  if (head === "report" || head === "email" || head === "mail") return cmdReport();
  if (head === "stop") {
    jarvisStop();
    return { ok: true, reply: "Stopped.", speak: false };
  }
  if (head === "speak") {
    const on = parts[1] === "on" || parts[1] === "1" || parts[1] === "true";
    const off = parts[1] === "off" || parts[1] === "0" || parts[1] === "false";
    if (!on && !off) return { ok: false, reply: "Usage: speak on|off" };
    const prefs = loadFocusJarvisPrefs();
    saveFocusJarvisPrefs({ ...prefs, speak: on });
    return { ok: true, reply: on ? "Speak on." : "Speak off.", speak: on };
  }
  if (head === "voice") {
    const mode = parts[1] as JarvisVoiceMode | undefined;
    if (mode !== "jarvis" && mode !== "normal" && mode !== "nvidia") {
      return { ok: false, reply: "Usage: voice jarvis|normal|nvidia" };
    }
    const prefs = loadFocusJarvisPrefs();
    saveFocusJarvisPrefs({
      ...prefs,
      voiceMode: mode,
      rate: mode === "jarvis" ? 0.92 : 1,
      pitch: mode === "jarvis" ? 0.88 : 1,
      voiceURI: "",
    });
    return { ok: true, reply: `Voice ${mode}.`, speak: true };
  }
  if (head === "session" && (parts[1] === "end" || parts[1] === "stop")) {
    return cmdSessionEnd();
  }
  if (head === "softland" || head === "sl") {
    if (parts[1] === "on") return cmdSoftland(true);
    if (parts[1] === "off") return cmdSoftland(false, parts[2]);
    return { ok: false, reply: "Usage: softland on | softland off UNLOCK" };
  }
  if (head === "pass" || head === "daypass") return cmdPass();
  if (head === "winddown" || head === "wind") {
    if (!isFocusEnforcerBridgeAvailable()) {
      return { ok: false, reply: "Enforcer bridge unavailable." };
    }
    const res = await enforcerNativeCmd("softland.emergency_winddown", {});
    if (!res || res.ok === false) {
      return { ok: false, reply: `Wind-down: ${res?.error || "failed"}`, source: "cmd" };
    }
    return { ok: true, reply: "Emergency wind-down set.", speak: true, source: "cmd" };
  }

  if (head === "close" || head === "kill") {
    const { isPcAppsBridgeAvailable, pcAppsCmd } = await import("./focusPcApps");
    if (!isPcAppsBridgeAvailable()) {
      return { ok: false, reply: "Close apps needs Focus desktop.", source: "cmd" };
    }
    if (parts[1] === "browsers" || parts[1] === "browser") {
      const r = await pcAppsCmd("browsers");
      return { ok: Boolean(r?.ok), reply: r?.detail || r?.error || "done", source: "cmd" };
    }
    const names =
      parts[1] === "app" || parts[1] === "apps"
        ? parts.slice(2).join(" ").replace(/[,;]/g, " ")
        : parts.slice(1).join(" ").replace(/[,;]/g, " ");
    if (!names.trim()) {
      return { ok: false, reply: "Usage: close browsers | close app name.exe", source: "cmd" };
    }
    const r = await pcAppsCmd("named", names.trim());
    return { ok: Boolean(r?.ok), reply: r?.detail || r?.error || "done", source: "cmd" };
  }

  if (head === "lock" || head === "sleep" || head === "shutdown" || head === "off") {
    const { isPcPowerBridgeAvailable, pcPowerCmd } = await import("./focusPcPower");
    if (!isPcPowerBridgeAvailable()) {
      return { ok: false, reply: "PC power needs Focus desktop (calt_focus)." };
    }
    if (head === "lock") {
      const r = await pcPowerCmd("lock");
      return {
        ok: Boolean(r?.ok),
        reply: r?.ok ? "PC locked." : `Lock failed: ${r?.detail || r?.error || "failed"}`,
        speak: Boolean(r?.ok),
        source: "cmd",
      };
    }
    if (head === "sleep") {
      const r = await pcPowerCmd("sleep");
      return {
        ok: Boolean(r?.ok),
        reply: r?.ok ? "PC sleeping." : `Sleep failed: ${r?.detail || r?.error || "failed"}`,
        speak: Boolean(r?.ok),
        source: "cmd",
      };
    }
    if (parts[1] === "cancel" || parts[1] === "abort") {
      const r = await pcPowerCmd("cancel");
      return {
        ok: Boolean(r?.ok),
        reply: r?.ok ? r.detail || "Shutdown cancelled." : `Cancel failed: ${r?.detail || r?.error}`,
        speak: Boolean(r?.ok),
        source: "cmd",
      };
    }
    let hasConfirm = false;
    let seconds = 30;
    const parseDelay = (tok: string): number => {
      const m = tok.match(/^(\d+)\s*([smhSMH])?$/);
      if (!m) return 0;
      const n = Number(m[1]);
      const u = (m[2] || "s").toLowerCase();
      if (u === "m") return n * 60;
      if (u === "h") return n * 3600;
      return n;
    };
    for (const p of parts.slice(1)) {
      if (p === "confirm") hasConfirm = true;
      else if (p === "in") continue;
      else {
        const d = parseDelay(p);
        if (d > 0) seconds = d;
      }
    }
    if (!hasConfirm) {
      return {
        ok: false,
        reply: "Usage: shutdown CONFIRM | shutdown 5m CONFIRM | shutdown cancel",
        source: "cmd",
      };
    }
    const r = await pcPowerCmd("shutdown", { seconds });
    return {
      ok: Boolean(r?.ok),
      reply: r?.ok
        ? r.detail || `Shutdown in ${seconds}s — type shutdown cancel to abort.`
        : `Shutdown failed: ${r?.detail || r?.error}`,
      speak: Boolean(r?.ok),
      source: "cmd",
    };
  }

  if (head === "model") {
    const {
      ensureOpenJarvisBrain,
      listLoadedOllamaModels,
      listOpenJarvisModels,
      brainStatusLine,
    } = await import("./focusOpenJarvisBrain");
    const name = parts.slice(1).join(" ").trim();
    if (!name) {
      const lineStatus = await brainStatusLine();
      return { ok: true, reply: lineStatus, speak: false, source: "cmd" };
    }
    const synced = await ensureOpenJarvisBrain(name);
    const loaded = await listLoadedOllamaModels();
    const models = await listOpenJarvisModels();
    return {
      ok: synced.ok,
      reply: synced.ok
        ? `Model → ${synced.prefs.model}. Available: ${models.slice(0, 8).join(", ") || "—"}. VRAM: ${loaded.join(", ") || "empty"}.`
        : `OpenJarvis down — ${synced.detail}`,
      speak: synced.ok,
      source: "cmd",
    };
  }

  if (head === "serve" || (head === "start" && parts[1] !== "session")) {
    const { ensureOpenJarvisBrain } = await import("./focusOpenJarvisBrain");
    const name = parts.slice(1).join(" ").trim();
    const r = await ensureOpenJarvisBrain(name || undefined);
    return {
      ok: r.ok,
      reply: r.ok ? `OpenJarvis API ready — ${r.detail}` : `Serve failed — ${r.detail}`,
      speak: r.ok,
      source: "cmd",
    };
  }

  if (head === "load" || head === "warm") {
    const { warmLocalModel, ensureOpenJarvisBrain } = await import("./focusOpenJarvisBrain");
    const name = parts.slice(1).join(" ").trim();
    if (name) await ensureOpenJarvisBrain(name);
    const r = await warmLocalModel(name || undefined);
    return {
      ok: r.ok,
      reply: r.ok ? `Loaded ${r.model}.` : `Load failed — ${r.detail}`,
      speak: r.ok,
      source: "cmd",
    };
  }

  if (head === "unload") {
    const { unloadLocalModel } = await import("./focusOpenJarvisBrain");
    const name = parts.slice(1).join(" ").trim();
    const r = await unloadLocalModel(name || undefined);
    return {
      ok: r.ok,
      reply: r.ok ? r.detail : `Unload failed — ${r.detail}`,
      speak: false,
      source: "cmd",
    };
  }

  if (head === "classify" || head === "categorize") {
    const { scanFocusClassifications } = await import("./focusOpenJarvisBrain");
    const r = await scanFocusClassifications(12);
    if (r.error) {
      return {
        ok: false,
        reply: `Classify failed — ${r.error}. Scanned ${r.scanned}.`,
        source: "cmd",
      };
    }
    const pending = r.suggestions.slice(0, 6);
    const lines = pending.map(
      (s) => `· ${s.label} → ${s.suggested_category} (${Math.round(s.confidence * 100)}%)`,
    );
    return {
      ok: true,
      reply:
        pending.length === 0
          ? `Scanned ${r.scanned}. No pending suggestions (approve in Settings → Classification).`
          : `Scanned ${r.scanned}, ${r.created} new.\n${lines.join("\n")}\nApprove in Settings → Classification.`,
      speak: true,
      source: "cmd",
    };
  }

  // Free text → conversational LLM chat (mutations stay command-only).
  if (line.length >= 2) {
    const ctx = await loadJarvisDayContext();
    const r = await jarvisChat(raw.trim().replace(/^\//, ""), ctx);
    if (r.line) {
      return {
        ok: r.source === "llm",
        reply: r.line,
        speak: r.source === "llm",
        source: r.source === "llm" ? "llm" : "canned",
      };
    }
  }

  return {
    ok: false,
    reply: `Unknown command. Try help.\n\n${FOCUS_COMMAND_HELP}`,
    speak: false,
    source: "cmd",
  };
}

async function loadJarvisDayContext(): Promise<JarvisContext> {
  const [rollup, loop, softland, enforcer] = await Promise.all([
    fetchJson("day_rollup.json"),
    fetchJson("day_loop.json"),
    fetchJson("softland_policy.json"),
    fetchJson("enforcer_status.json"),
  ]);
  const prod =
    typeof rollup?.productive_minutes === "number"
      ? Number(rollup.productive_minutes)
      : typeof rollup?.productive_seconds === "number"
        ? Math.floor(Number(rollup.productive_seconds) / 60)
        : undefined;
  const goal =
    typeof rollup?.daily_focus_minutes === "number"
      ? Number(rollup.daily_focus_minutes)
      : undefined;
  const tasks = Array.isArray(loop?.tasks)
    ? (loop!.tasks as { title?: string; done?: boolean }[])
        .filter((t) => !t.done && t.title)
        .map((t) => String(t.title))
        .slice(0, 6)
    : [];
  return {
    productiveMinutes: prod,
    goalMinutes: goal,
    bibleDone: Boolean(loop?.bible_done),
    planConfirmed: Boolean(loop?.plan_confirmed),
    planningEnabled:
      typeof loop?.planning_enabled === "boolean" ? Boolean(loop.planning_enabled) : undefined,
    mode: softland?.softland_enabled ? "softland" : "off",
    softlandOn: Boolean(
      softland?.softland_enabled ?? (softland as { enabled?: boolean } | null)?.enabled,
    ),
    armed: Boolean(enforcer?.armed),
    openTodos: tasks,
  };
}

/** Speak command reply when prefs allow. */
export function speakCommandReply(result: FocusCommandResult): void {
  if (!result.speak || !result.reply) return;
  const prefs = loadFocusJarvisPrefs();
  if (!prefs.enabled || !prefs.speak) return;
  // Don't speak the full help wall.
  if (result.reply.includes("help — this list")) return;
  jarvisSpeak(result.reply.slice(0, 400));
}
