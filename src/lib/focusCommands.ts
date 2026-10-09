/**
 * In-app Focus commands (Jarvis box). Same runner can later accept WhatsApp inbound.
 * Sensitive SoftLand/Arm changes keep server-side confirms — no bypass.
 */

import { focusDataUrl } from "../utils/focusDataUrl";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "./enforcerNativeCmd";
import {
  jarvisBrief,
  jarvisSpeak,
  jarvisStop,
  loadFocusJarvisPrefs,
  saveFocusJarvisPrefs,
  type JarvisVoiceMode,
} from "./focusJarvis";
import {
  loadWhatsAppReportPrefs,
  markWhatsAppReportSentToday,
  sendWhatsAppReportNow,
} from "./focusWhatsAppReport";

export type FocusCommandResult = {
  ok: boolean;
  reply: string;
  /** Spoken when Jarvis speak is on. */
  speak?: boolean;
};

export const FOCUS_COMMAND_HELP = [
  "help — this list",
  "brief — morning / day brief",
  "status — SoftLand, Arm, productive minutes",
  "report — WhatsApp daily report (opens chats)",
  "speak on|off — Jarvis voice",
  "voice jarvis|normal — voice model",
  "stop — stop speaking",
  "session end — end work session",
  "softland on — turn SoftLand on",
  "softland off UNLOCK — turn SoftLand off (must type UNLOCK)",
  "pass — try day pass / reward claim (bible required)",
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
  const prefs = loadWhatsAppReportPrefs();
  if (!prefs.members.length) {
    return {
      ok: false,
      reply: "No WhatsApp members — add them in Settings → More → WhatsApp report.",
    };
  }
  const r = await sendWhatsAppReportNow(prefs);
  if (!r.ok) return { ok: false, reply: r.error || "Could not open WhatsApp." };
  markWhatsAppReportSentToday();
  return {
    ok: true,
    reply: `Opened WhatsApp for ${r.opened} number${r.opened === 1 ? "" : "s"}. Tap Send in each chat.`,
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
  if (head === "report" || head === "whatsapp" || head === "wa") return cmdReport();
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
    if (mode !== "jarvis" && mode !== "normal") {
      return { ok: false, reply: "Usage: voice jarvis|normal" };
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

  // Free text → treat as brief topic via LLM brief (short)
  if (line.length >= 3 && !head.includes(".")) {
    const r = await jarvisBrief({
      openTodos: [line],
      mode: "command",
    });
    if (r.line) return { ok: true, reply: r.line, speak: true };
  }

  return {
    ok: false,
    reply: `Unknown command. Try help.\n\n${FOCUS_COMMAND_HELP}`,
    speak: false,
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
