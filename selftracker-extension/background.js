// ============================================================
// SelfTracker — background.js (Chromium MV3)
// Tracking / telemetry / Jarvis only. Blocking → calt-gate-extension.
// ============================================================

/* global GATE_API_URL, GATE_ALERT_URL, GATE_POLL_ACTIVE_S, GATE_ALERT_GAP_MS,
   isExtensionOrInternalUrl, DISTRACTION_DOMAINS, shouldBlockUrl, redirectTargetUrl,
   isCaltSpaUrl, blockKindForUrl, startBrowserTelemetry, FORCE_WATCH_HOSTS,
   isStrictDayMode, hostnameFromUrl, TEMP_ALLOW_STORAGE_KEY, TEMP_ALLOW_MS,
   pruneTempAllows, buildTempAllowGrant, upsertTempAllow, isTempAllowExcludedHost,
   tempAllowUntilForHost, browserPolicyOrFallback, isForceWatchHost, classifyHostCategory */

// Shared helpers are prepended by scripts/build_extension_workers.ps1 into service_worker.js
// (Edge MV3 importScripts often fails with NetworkError on unpacked paths).

/** DNR rule id range for watch hard-block (MV3 Edge/Chrome). */
var DNR_WATCH_RULE_BASE = 9100;

// Prefer chrome.* (callback-compatible). Firefox/Zen expose chrome + browser.
const extAPI = typeof chrome !== "undefined" && chrome.runtime ? chrome : browser;

let activeTabId = null;
let activeUrl = null;
let activeTitle = null;
let sessionStart = Date.now();
/** False when Edge loses OS focus — do not accrue internet time in background. */
let windowFocused = true;
let tabSwitchCount = 0;
let dailyLog = [];
let outboundQueue = [];
let ws = null;
/** @type {object|null} */
let gateCache = null;
let redirectsEnabled = true;
let lastGateFetchAt = 0;
let lastAlertAt = 0;
let gatePollTimer = null;
/** @type {number|null} */
let caltTabId = null;
let lastJarvisLine = "";
/** Last text we actually pushed to a tab (avoid poll spam restarting the toast). */
let lastJarvisBroadcast = "";
let lastRuleJarvisAt = 0;
/** Skip DNR updateDynamicRules when watch-block fingerprint unchanged (Edge crash guard). */
let lastDnrFingerprint = "";
/** Last soft-land target per tab — avoid tabs.update storms on the same URL. */
var softLandDone = Object.create(null);
var softLandInFlight = Object.create(null);
var lastEnforceAt = 0;
/** Enforce is rare (alarm ~1 min) — never on the light poll. */
var ENFORCE_MIN_GAP_MS = 60000;
var SOFTLAND_DEDUP_MS = 15000;
var MAX_ENFORCE_UPDATES = 2;
/** Cap DNR dynamic rules — Edge thrash if rule churn is huge. */
var MAX_DNR_WATCH_HOSTS = 8;
/** Circuit breaker: too many softLands → pause redirects (fail soft). */
var softLandRecentAt = [];
var SOFTLAND_STORM_MAX = 5;
var SOFTLAND_STORM_WINDOW_MS = 20000;
var REDIRECT_COOLDOWN_MS = 180000;
var redirectCooldownUntil = 0;
/** In-memory temp allows: { host, until }[] — synced with chrome.storage.local. */
var tempAllowsCache = [];

const BULK_FLUSH_MINUTES = 3;
const BULK_FLUSH_MAX = 25;

extAPI.storage.local.get(
  ["dailyLog", "tabSwitchCount", "outboundQueue", "gateCache", "redirectsEnabled", "caltTabId", "lastJarvisLine", "tempAllows"],
  (result) => {
    if (result.dailyLog) dailyLog = result.dailyLog;
    if (result.tabSwitchCount) tabSwitchCount = result.tabSwitchCount;
    if (Array.isArray(result.outboundQueue)) outboundQueue = result.outboundQueue;
    if (result.gateCache) gateCache = result.gateCache;
    if (typeof result.redirectsEnabled === "boolean") redirectsEnabled = result.redirectsEnabled;
    if (typeof result.caltTabId === "number") caltTabId = result.caltTabId;
    if (result.lastJarvisLine) {
      lastJarvisLine = String(result.lastJarvisLine);
      // Seed so the first post-restart poll does not re-toast a stale API line.
      lastJarvisBroadcast = lastJarvisLine;
    }
    if (Array.isArray(result.tempAllows)) {
      tempAllowsCache = pruneTempAllows(result.tempAllows, Date.now());
    }
  },
);

function scheduleAlarms() {
  extAPI.alarms.create("flush", { periodInMinutes: BULK_FLUSH_MINUTES });
  extAPI.alarms.create("ws-keepalive", { periodInMinutes: 2 });
  // Idle backup — Chrome alarms min ~1 min; active refresh uses setInterval ~4s
  extAPI.alarms.create("gate-poll", { periodInMinutes: 1 });
}

function startLightGatePoll() {
  if (gatePollTimer) return;
  // Slower than 4s — Edge crashes when SW wakes + DNR churn too often.
  var ms = Math.max(8000, Math.min(15000, (GATE_POLL_ACTIVE_S || 4) * 2000));
  gatePollTimer = setInterval(function () {
    // Cache + DNR fingerprint only — NEVER enforce/tabs.query on this timer.
    void pollDistractionGate({ opportunistic: true, enforce: false });
    void pollCaltTabCommand();
  }, ms);
}

function redirectsPausedByCircuit() {
  return redirectCooldownUntil && Date.now() < redirectCooldownUntil;
}

function noteSoftLandAttempt() {
  var now = Date.now();
  softLandRecentAt.push(now);
  while (softLandRecentAt.length && now - softLandRecentAt[0] > SOFTLAND_STORM_WINDOW_MS) {
    softLandRecentAt.shift();
  }
  if (softLandRecentAt.length >= SOFTLAND_STORM_MAX) {
    redirectCooldownUntil = now + REDIRECT_COOLDOWN_MS;
    softLandRecentAt = [];
    console.warn(
      "SelfTracker: softLand circuit breaker — redirects paused",
      REDIRECT_COOLDOWN_MS / 1000,
      "s (fail soft; Edge stay alive)",
    );
    return true;
  }
  return false;
}

extAPI.runtime.onInstalled.addListener(() => {
  scheduleAlarms();
  startLightGatePoll();
  connectWebSocket();
  pollDistractionGate();
});

extAPI.runtime.onStartup.addListener(() => {
  scheduleAlarms();
  startLightGatePoll();
  connectWebSocket();
  pollDistractionGate();
});

scheduleAlarms();
startLightGatePoll();
connectWebSocket();
pollDistractionGate();
try {
  startBrowserTelemetry(extAPI, function () {
    return gateCache;
  });
} catch (e) {
  console.warn("SelfTracker: telemetry start failed", e);
}

function connectWebSocket() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }
  try {
    ws = new WebSocket("ws://localhost:8000/ws/behavior");
    ws.onopen = () => {
      console.log("SelfTracker: connected to backend");
      extAPI.alarms.clear("ws-retry");
      flushOutboundQueue();
    };
    ws.onmessage = () => {};
    ws.onclose = () => {
      console.log("SelfTracker: backend disconnected — retry in 5s");
      ws = null;
      extAPI.alarms.create("ws-retry", { delayInMinutes: 5 / 60 });
    };
    ws.onerror = () => {
      ws = null;
    };
  } catch (e) {
    console.warn("SelfTracker: WebSocket unavailable", e);
    extAPI.alarms.create("ws-retry", { delayInMinutes: 10 / 60 });
  }
}

function caltExtensionHeaders() {
  var mode = "";
  try {
    mode = String((gateCache && gateCache.browser && gateCache.browser.mode) || "");
  } catch (e) {
    mode = "";
  }
  var paused = false;
  try {
    paused = typeof redirectsPausedByCircuit === "function" && redirectsPausedByCircuit();
  } catch (e2) {
    paused = false;
  }
  return {
    "X-CALT-Extension": "selftracker",
    "X-CALT-Ext-Mode": mode,
    "X-CALT-Ext-Circuit": paused ? "1" : "0",
    "X-CALT-Ext-Paused": redirectsEnabled === false ? "1" : "0",
  };
}

async function pollDistractionGate(opts) {
  opts = opts || {};
  // Default: light poll refreshes cache/DNR only. Full tab sweep only when enforce:true
  // (1 min alarm / explicit REFRESH / toggle redirects).
  var doEnforce = opts.enforce === true;
  var now = Date.now();
  if (opts.opportunistic && lastGateFetchAt && now - lastGateFetchAt < (GATE_POLL_ACTIVE_S || 4) * 1000) {
    return;
  }
  try {
    const r = await fetch(GATE_API_URL, { cache: "no-store", headers: caltExtensionHeaders() });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const g = await r.json();
    lastGateFetchAt = Date.now();
    const morning = g.morning || {};
    const browser = g.browser || {};
    gateCache = {
      ok: true,
      stale: false,
      degraded: false,
      fetched_at: lastGateFetchAt,
      locked: Boolean(g.locked),
      unlocked: Boolean(g.unlocked),
      enabled: Boolean(g.enabled),
      remaining_minutes: g.remaining_minutes ?? null,
      chapter_goal_met: Boolean(g.chapter_goal_met),
      day_unlimited: Boolean(g.day_unlimited),
      day_pass: Boolean(g.day_pass),
      reward_day: Boolean(g.reward_day),
      productive_minutes: g.productive_minutes ?? 0,
      daily_goal_minutes: g.daily_goal_minutes ?? 0,
      suggested_links: Array.isArray(g.suggested_links) ? g.suggested_links : [],
      current_block: g.current_block || null,
      morning: {
        next: morning.next || "open",
        bible_done: Boolean(morning.bible_done),
        plan_done: Boolean(morning.plan_done),
        bible_url: morning.bible_url || null,
        plan_url: morning.plan_url || null,
        redirect_url: morning.redirect_url || null,
        hint: morning.hint || "",
      },
      browser: browser,
      enforce: Boolean(browser.enforce) || Boolean(g.locked),
    };
    await extAPI.storage.local.set({ gateCache });
    // Blocking / DNR owned by CALT Gate — tracker only caches mode for UI + Jarvis.
  } catch (e) {
    // Fail-closed for study/bible — but NEVER re-arm YouTube block while already FREE.
    const err = String(e && e.message ? e.message : e);
    const prev = gateCache && typeof gateCache === "object" ? gateCache : null;
    const prevBrowser = (prev && prev.browser) || {};
    const prevMode = String(prevBrowser.mode || "").toLowerCase();
    const prevFree =
      prevMode === "free" ||
      Boolean(prev && (prev.day_unlimited || prev.reward_day || prev.unlocked));
    const keepStrict = !prevFree && ["bible", "planning", "study"].indexOf(prevMode) >= 0;
    const keepArmed = Boolean(prev && (prev.enabled || prev.locked || prev.enforce));
    if (prev && (prev.ok || prev.degraded) && (keepStrict || keepArmed || prevFree)) {
      const browser = Object.assign({}, prevBrowser, {
        // Keep FREE watch/social open across API blips; distraction filter stays on.
        block_watch_sites: prevFree ? false : true,
        block_social: prevFree ? false : prevBrowser.block_social === true,
        block_other: prevFree ? false : true,
        block_porn: prevBrowser.block_porn !== false,
        enforce: true,
        mode: prevFree ? "free" : prevMode || "study",
        mode_label: prevFree
          ? "FREE"
          : prevBrowser.mode_label || (prevMode || "study").toUpperCase(),
      });
      gateCache = Object.assign({}, prev, {
        ok: true,
        stale: true,
        degraded: true,
        fetched_at: Date.now(),
        error: err,
        enforce: true,
        day_unlimited: Boolean(prev.day_unlimited) || prevFree,
        reward_day: Boolean(prev.reward_day),
        unlocked: Boolean(prev.unlocked) || prevFree,
        browser: browser,
      });
    } else {
      // No usable cache: default fail-closed study (watch + adult blocked).
      gateCache = {
        ok: true,
        stale: true,
        degraded: true,
        fetched_at: Date.now(),
        locked: true,
        unlocked: false,
        enabled: true,
        enforce: true,
        error: err,
        morning: { next: "open", bible_done: false, plan_done: false },
        browser: {
          mode: "study",
          mode_label: "STUDY",
          enforce: true,
          block_watch_sites: true,
          block_social: true,
          block_other: true,
          block_porn: true,
          block_keywords: true,
        },
      };
    }
    await extAPI.storage.local.set({ gateCache });
  }
}

function lockedPageUrl() {
  return extAPI.runtime.getURL("locked.html");
}

/** locked.html?host=&from= so the interstitial can offer a 60s temp allow. */
function lockedPageUrlForBlocked(blockedUrl) {
  var base = lockedPageUrl();
  var host = "";
  try {
    host = typeof hostnameFromUrl === "function" ? hostnameFromUrl(blockedUrl) : "";
  } catch (e) {
    host = "";
  }
  if (!host) return base;
  var q = "host=" + encodeURIComponent(host);
  try {
    if (blockedUrl && String(blockedUrl).indexOf("http") === 0) {
      q += "&from=" + encodeURIComponent(String(blockedUrl).slice(0, 500));
    }
  } catch (e2) {
    /* ignore */
  }
  return base + "?" + q;
}

/** Attach pruned temp allows onto a gateCache copy for shouldBlockUrl. */
function gateCacheForBlockCheck() {
  if (!gateCache) return null;
  tempAllowsCache = pruneTempAllows(tempAllowsCache, Date.now());
  return Object.assign({}, gateCache, { temp_allows: tempAllowsCache });
}

async function persistTempAllows(list) {
  tempAllowsCache = pruneTempAllows(list, Date.now());
  var key = typeof TEMP_ALLOW_STORAGE_KEY !== "undefined" ? TEMP_ALLOW_STORAGE_KEY : "tempAllows";
  try {
    var payload = {};
    payload[key] = tempAllowsCache;
    await extAPI.storage.local.set(payload);
  } catch (e) {
    /* ignore */
  }
  return tempAllowsCache;
}

function reportGateAlert(kind, detail) {
  var now = Date.now();
  if (now - lastAlertAt < (GATE_ALERT_GAP_MS || 45000)) return;
  lastAlertAt = now;
  try {
    fetch(GATE_ALERT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: kind || "generic_rule_break", detail: detail || "" }),
      cache: "no-store",
    }).catch(function () {});
  } catch (e) {
    /* ignore */
  }
}

function watchBlockActive() {
  if (!redirectsEnabled) return false;
  if (!gateCache || (!gateCache.ok && !gateCache.degraded)) return false;
  var browser = gateCache.browser || {};
  var mode = String(browser.mode || "").toLowerCase();
  // Goal met / reward day / FREE → never DNR-redirect YouTube (porn filter stays on).
  if (typeof isFreeDay === "function" && isFreeDay(gateCache)) return false;
  if (mode === "free" || gateCache.day_unlimited || gateCache.reward_day || gateCache.unlocked) {
    return false;
  }
  if (browser.block_watch_sites) return true;
  return isStrictDayMode(mode);
}

/** Blocking moved to CALT Gate — keep stub so old call sites are harmless. */
async function syncDeclarativeWatchBlock() {
  return;
}

function caltSpaUrlPattern() {
  return [
    "http://localhost:5173/*",
    "http://127.0.0.1:5173/*",
  ];
}

async function findCaltTabs() {
  try {
    return await extAPI.tabs.query({ url: caltSpaUrlPattern() });
  } catch (e) {
    return [];
  }
}

async function sweepExtraCaltTabs() {
  // v1.5.13: NEVER tabs.remove for cleanup — closing tabs felt like Edge "closing".
  // Only remember the newest CALT SPA tab id for FOCUS_CALT reuse.
  var tabs = await findCaltTabs();
  if (!tabs || !tabs.length) return;
  tabs.sort(function (a, b) {
    return (b.id || 0) - (a.id || 0);
  });
  caltTabId = tabs[0].id;
  try {
    await extAPI.storage.local.set({ caltTabId: caltTabId });
  } catch (e) {
    /* ignore */
  }
}

function urlsRoughlyEqual(a, b) {
  if (!a || !b) return false;
  if (a === b) return true;
  // locked.html with/without query
  if (String(a).indexOf("locked.html") >= 0 && String(b).indexOf("locked.html") >= 0) return true;
  try {
    var ua = new URL(a);
    var ub = new URL(b);
    return ua.origin === ub.origin && ua.pathname === ub.pathname && ua.search === ub.search;
  } catch (e) {
    return false;
  }
}

/**
 * Ensure one primary CALT SPA tab at *spaUrl*.
 * Only for explicit FOCUS_CALT / OPEN_PATH / consumed tab commands — never gate poll.
 * Never windows.update focus (Edge crash / "closing" feel). Never tabs.remove.
 * Returns tab id or null.
 */
async function ensureOneCaltTab(spaUrl) {
  var tabs = await findCaltTabs();
  tabs = tabs || [];
  if (caltTabId != null) {
    try {
      var t = await extAPI.tabs.get(caltTabId);
      if (t && t.id != null) {
        // Already on target — activate only, skip URL rewrite + window thrash.
        if (t.url && urlsRoughlyEqual(t.url, spaUrl)) {
          try {
            await extAPI.tabs.update(t.id, { active: true });
          } catch (e) {
            /* ignore */
          }
          return t.id;
        }
        await extAPI.tabs.update(t.id, { url: spaUrl, active: true });
        // Do NOT windows.update({ focused: true }) — steals OS focus / thrash Edge.
        await sweepExtraCaltTabs();
        return t.id;
      }
    } catch (e) {
      caltTabId = null;
    }
  }
  if (tabs.length) {
    tabs.sort(function (a, b) {
      return (b.id || 0) - (a.id || 0);
    });
    caltTabId = tabs[0].id;
    try {
      var cur = tabs[0];
      if (cur && cur.url && urlsRoughlyEqual(cur.url, spaUrl)) {
        await extAPI.tabs.update(caltTabId, { active: true });
      } else {
        await extAPI.tabs.update(caltTabId, { url: spaUrl, active: true });
      }
      await extAPI.storage.local.set({ caltTabId: caltTabId });
    } catch (e) {
      /* ignore */
    }
    await sweepExtraCaltTabs();
    return caltTabId;
  }
  try {
    var created = await extAPI.tabs.create({ url: spaUrl, active: true });
    caltTabId = created && created.id != null ? created.id : null;
    if (caltTabId != null) {
      await extAPI.storage.local.set({ caltTabId: caltTabId });
    }
    return caltTabId;
  } catch (e) {
    return null;
  }
}

/**
 * Park ONLY the offending tab. Never focus other windows, never rewrite
 * unrelated tabs — that thrashed Edge and felt like a whole-browser block.
 *
 * Morning bible/plan: send this tab to the SPA soft-land URL.
 * Study / armed: send this tab to locked.html (DNR also covers YT main_frame).
 */
async function softLandBlockedTab(tabId, spaUrl) {
  if (tabId == null) return false;
  if (!redirectsEnabled || redirectsPausedByCircuit()) return false;
  var mode = "";
  var next = "";
  try {
    mode = String((gateCache && gateCache.browser && gateCache.browser.mode) || "").toLowerCase();
    next = String((gateCache && gateCache.morning && gateCache.morning.next) || "").toLowerCase();
  } catch (e) {
    /* ignore */
  }
  var morningSoft =
    next === "bible" ||
    next === "plan" ||
    mode === "bible" ||
    mode === "planning";
  // Study/armed: use spaUrl when it is locked.html (?host= for temp-allow UI).
  var target = lockedPageUrl();
  if (morningSoft && spaUrl && String(spaUrl).indexOf("locked.html") < 0) {
    target = spaUrl;
  } else if (spaUrl && String(spaUrl).indexOf("locked.html") >= 0) {
    target = spaUrl;
  }
  // In-flight / recent same-target: skip (onCommitted + rare enforce).
  if (softLandInFlight[tabId] === target) return false;
  var done = softLandDone[tabId];
  if (done && done.target === target && Date.now() - done.at < SOFTLAND_DEDUP_MS) {
    return false;
  }
  try {
    var existing = await extAPI.tabs.get(tabId);
    if (!existing) return false;
    var eu = existing.url ? String(existing.url) : "";
    if (eu.indexOf("locked.html") >= 0) {
      // Already parked. Morning may upgrade locked.html → bible/plan SPA once;
      // study stays on locked.html (DNR + softLand share that target).
      if (!morningSoft || String(target).indexOf("locked.html") >= 0) {
        softLandDone[tabId] = { target: target, at: Date.now() };
        return false;
      }
    }
    if (eu && isCaltSpaUrl(eu) && morningSoft) {
      softLandDone[tabId] = { target: target, at: Date.now() };
      return false;
    }
    if (eu && urlsRoughlyEqual(eu, target)) {
      softLandDone[tabId] = { target: target, at: Date.now() };
      return false;
    }
    // Count only real navigations toward the storm breaker.
    if (noteSoftLandAttempt()) return false;
    softLandInFlight[tabId] = target;
    // Do not set active:true — bulk enforce must not steal focus across tabs.
    await extAPI.tabs.update(tabId, { url: target });
    softLandDone[tabId] = { target: target, at: Date.now() };
    return true;
  } catch (e) {
    /* tab gone */
    return false;
  } finally {
    delete softLandInFlight[tabId];
  }
}

async function maybeRedirectTab() {
  // Blocking / softLand owned by CALT Gate (avoids double-hit Edge crashes).
  return false;
}

async function enforceDistractionRedirects() {
  // CRASH FIX: never mass tabs.query + tabs.update (Edge thrash).
  // Watch = DNR only. Other blocks = onCommitted softLand for that one tab.
  // Kept as a no-op hook so alarms / messages do not reintroduce the sweep.
  return;
}

function broadcastJarvisLine(kind) {
  var now = Date.now();
  // Gate enforce runs ~every 4s — do not restart the toast on every sweep.
  if (now - lastRuleJarvisAt < (GATE_ALERT_GAP_MS || 45000)) return;
  lastRuleJarvisAt = now;
  var text = "Rule break — " + (kind || "blocked");
  lastJarvisBroadcast = text;
  try {
    extAPI.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      if (!tabs || !tabs[0] || tabs[0].id == null) return;
      extAPI.tabs.sendMessage(
        tabs[0].id,
        { type: "JARVIS_LINE", text: text },
        function () {
          void extAPI.runtime.lastError;
        }
      );
    });
  } catch (e) {
    /* ignore */
  }
}

async function pollCaltTabCommand() {
  try {
    var r = await fetch(CALT_TAB_CMD_URL + "?consume=1", { cache: "no-store" });
    if (!r.ok) return;
    var data = await r.json();
    if (data && data.jarvis && data.jarvis.text) {
      var t = String(data.jarvis.text).trim();
      if (t) {
        lastJarvisLine = t;
        try {
          await extAPI.storage.local.set({ lastJarvisLine: lastJarvisLine });
        } catch (e) {
          /* ignore */
        }
        // Only push caption when the line *changes* — API returns the same
        // last_jarvis_line for up to ~1h on every ~4s poll (was an infinite toast loop).
        if (t !== lastJarvisBroadcast) {
          lastJarvisBroadcast = t;
          broadcastJarvisCaption(t);
        }
      }
    }
    var cmd = data && data.command;
    if (!cmd || !cmd.action) return;
    var path = cmd.path || "/";
    if (path.indexOf("http") === 0) {
      await ensureOneCaltTab(path);
    } else {
      var origin = typeof CALT_ORIGIN !== "undefined" ? CALT_ORIGIN : "http://localhost:5173";
      if (!path.startsWith("/")) path = "/" + path;
      await ensureOneCaltTab(origin + path);
    }
  } catch (e) {
    /* API down */
  }
}

function broadcastJarvisCaption(text) {
  try {
    extAPI.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      if (!tabs || !tabs[0] || tabs[0].id == null) return;
      extAPI.tabs.sendMessage(
        tabs[0].id,
        { type: "JARVIS_LINE", text: text },
        function () {
          void extAPI.runtime.lastError;
        }
      );
    });
  } catch (e) {
    /* ignore */
  }
}

function classifyUrl(url, title) {
  if (!url) return "Unknown";
  const u = url.toLowerCase();
  const t = String(title || "").toLowerCase();
  if (u.includes("localhost") || u.includes("127.0.0.1")) {
    if (
      u.includes("lecture-notes") ||
      u.includes("/bible") ||
      u.includes("/quiz") ||
      u.includes("/review") ||
      u.includes("/math") ||
      u.includes("/gre") ||
      u.includes("/vocab") ||
      t.includes("lecture notes") ||
      t.includes("study library")
    ) {
      return "Coursework";
    }
  }
  if (u.includes("github") || u.includes("gitlab") || u.includes("stackoverflow") || u.includes("docs.") || u.includes("developer.") || u.includes("mdn")) return "Dev / Docs";
  if (u.includes("notion") || u.includes("obsidian") || u.includes("roamresearch") || u.includes("logseq")) return "Knowledge Work";
  if (u.includes("figma") || u.includes("canva") || u.includes("excalidraw")) return "Design";
  if (u.includes("mail") || u.includes("gmail") || u.includes("outlook") || u.includes("calendar")) return "Admin / Email";
  if (u.includes("meet.google") || u.includes("zoom") || u.includes("teams.microsoft") || u.includes("discord")) return "Communication";
  if (u.includes("coursera") || u.includes("udemy") || u.includes("edx") || u.includes("khanacademy") || u.includes("leetcode") || u.includes("brilliant") || u.includes("scaler.com") || u.includes("scaler.")) return "Coursework";
  if (u.includes("wikipedia") || u.includes("arxiv") || u.includes("scholar.google") || u.includes("pubmed") || u.includes("jstor")) return "Research";
  if (u.includes("youtube") || u.includes("twitch") || u.includes("netflix") || u.includes("primevideo") || u.includes("disneyplus")) return "Video / Streaming";
  if (u.includes("reddit") || u.includes("twitter") || u.includes("x.com") || u.includes("instagram") || u.includes("tiktok") || u.includes("facebook") || u.includes("linkedin")) return "Social Media";
  if (u.includes("chess") || u.includes("steam") || u.includes("game") || u.includes("itch.io") || u.includes("kongregate")) return "Gaming";
  if (u.includes("spotify") || u.includes("soundcloud") || u.includes("music")) return "Music";
  if (u.includes("news") || u.includes("bbc") || u.includes("cnn") || u.includes("theguardian")) return "News";
  if (u.includes("amazon") || u.includes("flipkart") || u.includes("myntra") || u.includes("ebay")) return "Shopping";
  if (u === "chrome://newtab/" || u === "about:blank" || u === "") return "Idle / New Tab";
  return "Browsing";
}

function productivityScore(category) {
  const scores = {
    "Dev / Docs": 95, Research: 90, Coursework: 88, "Knowledge Work": 85,
    Design: 80, "Admin / Email": 55, Communication: 50, News: 35,
    Browsing: 30, Music: 25, Shopping: 20, "Social Media": 10,
    "Video / Streaming": 10, Gaming: 15, "Idle / New Tab": 0, Unknown: 0,
  };
  return scores[category] ?? 30;
}

function extractDomain(url) {
  try {
    return new URL(url).hostname.replace("www.", "");
  } catch {
    return "unknown";
  }
}

function enqueueOutbound(payload) {
  outboundQueue.push(payload);
  if (outboundQueue.length > 2000) outboundQueue = outboundQueue.slice(-2000);
  extAPI.storage.local.set({ outboundQueue });
  if (outboundQueue.length >= BULK_FLUSH_MAX) flushOutboundQueue();
}

function flushOutboundQueue() {
  if (!outboundQueue.length) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const batch = outboundQueue.splice(0, outboundQueue.length);
  extAPI.storage.local.set({ outboundQueue });
  try {
    ws.send(JSON.stringify({ type: "BATCH", events: batch, source: "extension" }));
  } catch (e) {
    outboundQueue = batch.concat(outboundQueue);
    extAPI.storage.local.set({ outboundQueue });
    console.warn("SelfTracker: batch flush failed", e);
  }
}

function logCurrentSession(reason = "tab_switch") {
  // CALT SPA (localhost) → study-presence only; never double-count as extension.
  if (isExtensionOrInternalUrl(activeUrl) || isCaltSpaUrl(activeUrl)) return;
  // Active focused window only (blur reason still flushes the previous focused slice).
  if (!windowFocused && reason !== "window_blur" && reason !== "idle") return;
  const duration = Math.round((Date.now() - sessionStart) / 1000);
  if (duration < 2) return;
  const category = classifyUrl(activeUrl, activeTitle);
  const entry = {
    timestamp: sessionStart,
    end_timestamp: Date.now(),
    duration_seconds: duration,
    url: activeUrl,
    title: activeTitle || "Untitled",
    domain: extractDomain(activeUrl),
    category,
    productivity_score: productivityScore(category),
    reason,
    tab_switches_today: tabSwitchCount,
    gate_locked: Boolean(gateCache && gateCache.locked),
    active_tab_only: true,
  };
  dailyLog.push(entry);
  if (dailyLog.length > 5000) dailyLog = dailyLog.slice(-5000);
  extAPI.storage.local.set({ dailyLog, lastEntry: entry, tabSwitchCount });
  enqueueOutbound({ type: "SESSION_END", source: "extension", ...entry });
}

extAPI.tabs.onActivated.addListener(async (info) => {
  logCurrentSession("tab_switch");
  tabSwitchCount++;
  try {
    const tab = await extAPI.tabs.get(info.tabId);
    activeTabId = info.tabId;
    activeUrl = tab.url;
    activeTitle = tab.title;
    sessionStart = Date.now();
    // Do not softLand on every tab focus — Edge crash / redirect storms.
    // Blocking is DNR + webNavigation.onCommitted only.
  } catch {
    /* tab may be gone */
  }
});

extAPI.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  // v1.5.13: softLand ONLY via webNavigation.onCommitted (single committed tab).
  // onUpdated loading/complete + URL change stacked with onCommitted → Edge crash.
  if (tabId !== activeTabId) return;
  if (changeInfo.status !== "complete") return;
  logCurrentSession("navigation");
  activeUrl = tab.url;
  activeTitle = tab.title;
  sessionStart = Date.now();
});

// softLand / onCommitted redirects moved to calt-gate-extension.

if (extAPI.tabs.onRemoved) {
  extAPI.tabs.onRemoved.addListener(function (tabId) {
    delete softLandDone[tabId];
    delete softLandInFlight[tabId];
  });
}

extAPI.windows.onFocusChanged.addListener((windowId) => {
  if (windowId === extAPI.windows.WINDOW_ID_NONE) {
    logCurrentSession("window_blur");
    windowFocused = false;
  } else {
    windowFocused = true;
    sessionStart = Date.now();
  }
});

if (extAPI.idle && extAPI.idle.setDetectionInterval) {
  extAPI.idle.setDetectionInterval(60);
  extAPI.idle.onStateChanged.addListener((state) => {
    if (state === "idle" || state === "locked") {
      logCurrentSession("idle");
    } else if (state === "active") {
      sessionStart = Date.now();
    }
  });
}

extAPI.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "ws-retry" || alarm.name === "ws-keepalive") {
    connectWebSocket();
    return;
  }
  if (alarm.name === "gate-poll") {
    // ~1 min: refresh + rare enforce sweep (not the 4s light poll).
    void pollDistractionGate({ enforce: true });
    return;
  }
  if (alarm.name === "flush") {
    flushOutboundQueue();
    if (
      windowFocused &&
      activeUrl &&
      !isExtensionOrInternalUrl(activeUrl) &&
      !isCaltSpaUrl(activeUrl)
    ) {
      const category = classifyUrl(activeUrl, activeTitle);
      const liveEntry = {
        timestamp: sessionStart,
        end_timestamp: Date.now(),
        duration_seconds: Math.round((Date.now() - sessionStart) / 1000),
        url: activeUrl,
        title: activeTitle || "Untitled",
        domain: extractDomain(activeUrl),
        category,
        productivity_score: productivityScore(category),
        reason: "live",
        tab_switches_today: tabSwitchCount,
        gate_locked: Boolean(gateCache && gateCache.locked),
        active_tab_only: true,
      };
      extAPI.storage.local.set({ liveEntry });
    }
  }
});

extAPI.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "BEHAVIORAL_UPDATE") {
    const rawPayload = {
      type: "BEHAVIORAL_UPDATE",
      timestamp: Date.now(),
      url: sender.tab?.url || "",
      domain: sender.tab?.url ? extractDomain(sender.tab.url) : "",
      gate_locked: Boolean(gateCache && gateCache.locked),
      ...msg.data,
    };
    extAPI.storage.local.get(["behavioralLog"], (result) => {
      const log = result.behavioralLog || [];
      log.push(rawPayload);
      if (log.length > 2000) log.splice(0, log.length - 2000);
      extAPI.storage.local.set({ behavioralLog: log });
    });
    enqueueOutbound(rawPayload);
    return false;
  }

  if (msg.type === "GET_STATS") {
    extAPI.storage.local.get(
      ["dailyLog", "behavioralLog", "tabSwitchCount", "liveEntry", "gateCache", "redirectsEnabled"],
      (result) => {
        sendResponse({ type: "STATS_RESPONSE", data: result });
      },
    );
    return true;
  }

  if (msg.type === "GET_GATE") {
    sendResponse({ gateCache, redirectsEnabled, domains: DISTRACTION_DOMAINS });
    return false;
  }

  if (msg.type === "SET_REDIRECTS") {
    // Informational only — real toggle is in CALT Gate popup.
    redirectsEnabled = Boolean(msg.enabled);
    extAPI.storage.local.set({ redirectsEnabled });
    sendResponse({
      ok: true,
      redirectsEnabled,
      note: "Site blocking is handled by CALT Gate — toggle redirects there.",
    });
    return false;
  }

  if (msg.type === "REFRESH_GATE") {
    pollDistractionGate({ enforce: true }).then(() => sendResponse({ gateCache })).catch(() => sendResponse({ gateCache }));
    return true;
  }

  if (msg.type === "FOCUS_CALT" || msg.type === "OPEN_PATH") {
    var path = msg.path || "/bible";
    var origin = typeof CALT_ORIGIN !== "undefined" ? CALT_ORIGIN : "http://localhost:5173";
    var url = path.indexOf("http") === 0 ? path : origin + (path.startsWith("/") ? path : "/" + path);
    ensureOneCaltTab(url).then(function (id) {
      sendResponse({ ok: true, tabId: id });
    }).catch(function () {
      sendResponse({ ok: false });
    });
    return true;
  }

  if (msg.type === "GET_JARVIS") {
    sendResponse({ text: lastJarvisLine || "", gateCache: gateCache });
    return false;
  }

  if (msg.type === "TEMP_ALLOW_STATUS") {
    var hostS = String(msg.host || "").toLowerCase().replace(/^www\./, "");
    tempAllowsCache = pruneTempAllows(tempAllowsCache, Date.now());
    var polS = browserPolicyOrFallback(gateCache && gateCache.browser);
    var excludedS = !hostS || isTempAllowExcludedHost(hostS, polS);
    var untilS = tempAllowUntilForHost(hostS, tempAllowsCache, Date.now());
    sendResponse({
      ok: true,
      host: hostS,
      excluded: excludedS,
      can_allow: Boolean(hostS) && !excludedS,
      allowed_until: untilS || 0,
      temp_allow_ms: typeof TEMP_ALLOW_MS !== "undefined" ? TEMP_ALLOW_MS : 60000,
      temp_allows: tempAllowsCache,
    });
    return false;
  }

  if (msg.type === "TEMP_ALLOW_REQUEST") {
    var hostR = String(msg.host || "").toLowerCase().replace(/^www\./, "");
    var nowR = Date.now();
    var polR = browserPolicyOrFallback(gateCache && gateCache.browser);
    var grant = buildTempAllowGrant(hostR, nowR, polR);
    if (!grant.ok) {
      sendResponse({
        ok: false,
        error: grant.error || "This site can't be temporarily allowed",
        host: hostR,
      });
      return false;
    }
    tempAllowsCache = upsertTempAllow(tempAllowsCache, grant.entry, nowR);
    persistTempAllows(tempAllowsCache).then(function () {
      sendResponse({
        ok: true,
        host: grant.entry.host,
        until: grant.entry.until,
        temp_allow_ms: typeof TEMP_ALLOW_MS !== "undefined" ? TEMP_ALLOW_MS : 60000,
      });
    }).catch(function () {
      sendResponse({
        ok: true,
        host: grant.entry.host,
        until: grant.entry.until,
        temp_allow_ms: typeof TEMP_ALLOW_MS !== "undefined" ? TEMP_ALLOW_MS : 60000,
      });
    });
    return true;
  }

  if (msg.type === "EXPORT_CSV") {
    extAPI.storage.local.get(["dailyLog"], (result) => {
      sendResponse({ type: "CSV_READY", data: result.dailyLog || [] });
    });
    return true;
  }

  if (msg.type === "CLEAR_DATA") {
    dailyLog = [];
    tabSwitchCount = 0;
    extAPI.storage.local.set({ dailyLog: [], behavioralLog: [], tabSwitchCount: 0, liveEntry: null });
    sendResponse({ ok: true });
    return false;
  }

  if (msg.type === "PING") {
    sendResponse({ ok: true, ws: ws?.readyState ?? WebSocket.CLOSED });
    return false;
  }

  return false;
});
