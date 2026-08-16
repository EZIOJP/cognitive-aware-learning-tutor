// ============================================================
// CALT Gate — blocker only (MV3 DNR + light softLand)
// No telemetry / WebSocket. Pair with CALT SelfTracker.
// Watch hosts = DNR only. Other blocks = one-tab softLand.
// ============================================================

/* global GATE_API_URL, GATE_ALERT_URL, GATE_ALERT_GAP_MS, FORCE_WATCH_HOSTS,
   FORCE_PORN_HOSTS, isStrictDayMode, TEMP_ALLOW_STORAGE_KEY, TEMP_ALLOW_MS, pruneTempAllows,
   buildTempAllowGrant, upsertTempAllow, isTempAllowExcludedHost,
   tempAllowUntilForHost, browserPolicyOrFallback, shouldBlockUrl,
   redirectTargetUrl, isCaltSpaUrl, blockKindForUrl, hostnameFromUrl,
   isForceWatchHost, isForcePornHost, classifyHostCategory, isExtensionOrInternalUrl,
   CALT_BIBLE_URL, CALT_PRODUCTIVITY_URL */

// Shared helpers are prepended by scripts/build_extension_workers.ps1 into service_worker.js

var DNR_WATCH_RULE_BASE = 9200;
var MAX_DNR_WATCH_HOSTS = 8;
/** Hard-block distraction hosts in every mode (including FREE). */
var DNR_PORN_RULE_BASE = 9300;
var MAX_DNR_PORN_HOSTS = 40;
var GATE_POLL_MS = 12000;
var SOFTLAND_DEDUP_MS = 15000;

var extAPI = typeof chrome !== "undefined" && chrome.runtime ? chrome : browser;

var gateCache = null;
var redirectsEnabled = true;
var lastGateFetchAt = 0;
var lastDnrFingerprint = "";
var lastDnrPornFingerprint = "";
var gatePollTimer = null;
var lastAlertAt = 0;
var softLandDone = Object.create(null);
var softLandInFlight = Object.create(null);
var tempAllowsCache = [];

extAPI.storage.local.get(["gateCache", "redirectsEnabled", "tempAllows"], function (result) {
  if (result.gateCache) gateCache = result.gateCache;
  if (typeof result.redirectsEnabled === "boolean") redirectsEnabled = result.redirectsEnabled;
  if (Array.isArray(result.tempAllows)) {
    tempAllowsCache =
      typeof pruneTempAllows === "function" ? pruneTempAllows(result.tempAllows, Date.now()) : result.tempAllows;
  }
});

function lockedPageUrl() {
  return extAPI.runtime.getURL("locked.html");
}

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

function gateCacheForBlockCheck() {
  if (!gateCache) return null;
  return Object.assign({}, gateCache, { temp_allows: tempAllowsCache, tempAllows: tempAllowsCache });
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
  // Reward day / goal unlock must clear YouTube DNR (softLand alone is not enough).
  if (typeof isFreeDay === "function" && isFreeDay(gateCache)) return false;
  var browser = gateCache.browser || {};
  var mode = String(browser.mode || "").toLowerCase();
  if (mode === "free" || gateCache.day_unlimited || gateCache.reward_day || gateCache.unlocked) {
    return false;
  }
  if (browser.block_watch_sites) return true;
  return typeof isStrictDayMode === "function" && isStrictDayMode(mode);
}

async function syncDeclarativeWatchBlock(opts) {
  opts = opts || {};
  if (!extAPI.declarativeNetRequest || !extAPI.declarativeNetRequest.updateDynamicRules) {
    return;
  }
  var raw = typeof FORCE_WATCH_HOSTS !== "undefined" ? FORCE_WATCH_HOSTS : ["youtube.com", "youtu.be"];
  var hosts = raw.slice(0, MAX_DNR_WATCH_HOSTS);
  var active = watchBlockActive();
  var fingerprint = (active ? "1" : "0") + "|" + hosts.join(",");
  if (!opts.force && fingerprint === lastDnrFingerprint) return;

  var removeIds = [];
  for (var i = 0; i < MAX_DNR_WATCH_HOSTS + 4; i++) removeIds.push(DNR_WATCH_RULE_BASE + i);

  try {
    if (!active) {
      await extAPI.declarativeNetRequest.updateDynamicRules({
        removeRuleIds: removeIds,
        addRules: [],
      });
      lastDnrFingerprint = fingerprint;
      return;
    }
    var target = lockedPageUrl();
    var addRules = [];
    for (var j = 0; j < hosts.length; j++) {
      addRules.push({
        id: DNR_WATCH_RULE_BASE + j,
        priority: 100,
        action: { type: "redirect", redirect: { url: target } },
        condition: {
          requestDomains: [hosts[j]],
          resourceTypes: ["main_frame"],
        },
      });
    }
    await extAPI.declarativeNetRequest.updateDynamicRules({
      removeRuleIds: removeIds,
      addRules: addRules,
    });
    lastDnrFingerprint = fingerprint;
  } catch (e) {
    console.warn("CALT Gate: DNR watch sync failed", e);
  }
}

/** Always-on DNR for distraction hosts (FREE + study). SoftLand is backup only. */
async function syncDeclarativePornBlock(opts) {
  opts = opts || {};
  if (!extAPI.declarativeNetRequest || !extAPI.declarativeNetRequest.updateDynamicRules) {
    return;
  }
  var raw =
    typeof FORCE_PORN_HOSTS !== "undefined" && FORCE_PORN_HOSTS.length
      ? FORCE_PORN_HOSTS
      : ["pornhub.com", "xvideos.com", "erome.com"];
  var hosts = raw.slice(0, MAX_DNR_PORN_HOSTS);
  var active = redirectsEnabled !== false;
  var fingerprint = (active ? "1" : "0") + "|porn|" + hosts.join(",");
  if (!opts.force && fingerprint === lastDnrPornFingerprint) return;

  var removeIds = [];
  for (var i = 0; i < MAX_DNR_PORN_HOSTS + 4; i++) removeIds.push(DNR_PORN_RULE_BASE + i);

  try {
    if (!active) {
      await extAPI.declarativeNetRequest.updateDynamicRules({
        removeRuleIds: removeIds,
        addRules: [],
      });
      lastDnrPornFingerprint = fingerprint;
      return;
    }
    var target = lockedPageUrl();
    var addRules = [];
    for (var j = 0; j < hosts.length; j++) {
      addRules.push({
        id: DNR_PORN_RULE_BASE + j,
        priority: 110,
        action: { type: "redirect", redirect: { url: target } },
        condition: {
          requestDomains: [hosts[j]],
          resourceTypes: ["main_frame"],
        },
      });
    }
    await extAPI.declarativeNetRequest.updateDynamicRules({
      removeRuleIds: removeIds,
      addRules: addRules,
    });
    lastDnrPornFingerprint = fingerprint;
  } catch (e) {
    console.warn("CALT Gate: DNR distraction sync failed", e);
  }
}

async function pollGate() {
  var now = Date.now();
  if (lastGateFetchAt && now - lastGateFetchAt < GATE_POLL_MS - 500) return;
  try {
    var r = await fetch(GATE_API_URL, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    var g = await r.json();
    lastGateFetchAt = Date.now();
    var morning = g.morning || {};
    var browser = g.browser || {};
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
    await extAPI.storage.local.set({ gateCache: gateCache });
    var modeNow = String(browser.mode || "").toLowerCase();
    var freeNow =
      Boolean(g.day_unlimited) || Boolean(g.reward_day) || modeNow === "free";
    await syncDeclarativeWatchBlock({
      force: freeNow || modeNow === "study",
    });
    await syncDeclarativePornBlock({ force: true });
  } catch (e) {
    var err = String(e && e.message ? e.message : e);
    var prev = gateCache && typeof gateCache === "object" ? gateCache : null;
    var prevBrowser = (prev && prev.browser) || {};
    var prevMode = String(prevBrowser.mode || "").toLowerCase();
    var prevFree =
      prevMode === "free" ||
      Boolean(prev && (prev.day_unlimited || prev.reward_day || prev.unlocked));
    if (prev && (prev.ok || prev.degraded)) {
      gateCache = Object.assign({}, prev, {
        ok: true,
        stale: true,
        degraded: true,
        fetched_at: Date.now(),
        error: err,
        day_unlimited: Boolean(prev.day_unlimited) || prevFree,
        reward_day: Boolean(prev.reward_day),
        unlocked: Boolean(prev.unlocked) || prevFree,
        browser: Object.assign({}, prevBrowser, {
          block_watch_sites: prevFree ? false : true,
          block_social: prevFree ? false : prevBrowser.block_social === true,
          block_other: prevFree ? false : true,
          block_porn: prevBrowser.block_porn !== false,
          mode: prevFree ? "free" : prevMode || "study",
          mode_label: prevFree ? "FREE" : prevBrowser.mode_label || "STUDY",
          enforce: true,
        }),
      });
    } else {
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
    await extAPI.storage.local.set({ gateCache: gateCache });
    await syncDeclarativeWatchBlock({ force: true });
    await syncDeclarativePornBlock({ force: true });
  }
}

function startPoll() {
  if (gatePollTimer) return;
  gatePollTimer = setInterval(function () {
    void pollGate();
  }, GATE_POLL_MS);
}

extAPI.alarms.create("gate-poll", { periodInMinutes: 1 });
extAPI.alarms.onAlarm.addListener(function (alarm) {
  if (alarm.name === "gate-poll") void pollGate();
});

extAPI.runtime.onInstalled.addListener(function () {
  startPoll();
  void pollGate();
});
extAPI.runtime.onStartup.addListener(function () {
  startPoll();
  void pollGate();
});

startPoll();
void pollGate();

async function softLandBlockedTab(tabId, spaUrl) {
  if (tabId == null || !redirectsEnabled) return false;
  var mode = "";
  var next = "";
  try {
    mode = String((gateCache && gateCache.browser && gateCache.browser.mode) || "").toLowerCase();
    next = String((gateCache && gateCache.morning && gateCache.morning.next) || "").toLowerCase();
  } catch (e) {
    /* ignore */
  }
  var morningSoft =
    next === "bible" || next === "plan" || mode === "bible" || mode === "planning";
  var target = lockedPageUrl();
  if (morningSoft && spaUrl && String(spaUrl).indexOf("locked.html") < 0) {
    target = spaUrl;
  } else if (spaUrl && String(spaUrl).indexOf("locked.html") >= 0) {
    target = spaUrl;
  }
  if (softLandInFlight[tabId] === target) return false;
  var done = softLandDone[tabId];
  if (done && done.target === target && Date.now() - done.at < SOFTLAND_DEDUP_MS) return false;
  try {
    var existing = await extAPI.tabs.get(tabId);
    if (!existing) return false;
    var eu = existing.url ? String(existing.url) : "";
    if (eu.indexOf("locked.html") >= 0) {
      if (!morningSoft || String(target).indexOf("locked.html") >= 0) {
        softLandDone[tabId] = { target: target, at: Date.now() };
        return false;
      }
    }
    if (eu && typeof isCaltSpaUrl === "function" && isCaltSpaUrl(eu) && morningSoft) {
      softLandDone[tabId] = { target: target, at: Date.now() };
      return false;
    }
    softLandInFlight[tabId] = target;
    await extAPI.tabs.update(tabId, { url: target });
    softLandDone[tabId] = { target: target, at: Date.now() };
    return true;
  } catch (e) {
    return false;
  } finally {
    delete softLandInFlight[tabId];
  }
}

async function maybeRedirectTab(tabId, url, title) {
  if (!redirectsEnabled) return false;
  var gc = gateCacheForBlockCheck();
  if (!gc || (!gc.ok && !gc.degraded)) return false;
  if (!url || (typeof isExtensionOrInternalUrl === "function" && isExtensionOrInternalUrl(url))) return false;
  if (url.indexOf("locked.html") >= 0) return false;
  if (typeof isCaltSpaUrl === "function" && isCaltSpaUrl(url)) return false;

  var host = "";
  try {
    host = typeof hostnameFromUrl === "function" ? hostnameFromUrl(url) : "";
  } catch (e) {
    host = "";
  }
  // Watch / distraction hosts = DNR only — never also softLand (Edge double-hit crash).
  if (host && typeof isForceWatchHost === "function" && isForceWatchHost(host) && watchBlockActive()) {
    return false;
  }
  if (host && typeof isForcePornHost === "function" && isForcePornHost(host)) {
    return false;
  }
  if (!shouldBlockUrl(url, gc, title || "")) return false;
  var browser = gc.browser || {};
  var cat =
    typeof classifyHostCategory === "function"
      ? classifyHostCategory(host, browserPolicyOrFallback(browser))
      : "";
  if (cat === "watch" && watchBlockActive()) return false;

  var kind = typeof blockKindForUrl === "function" ? blockKindForUrl(url, gc, title || "") : "blocked";
  reportGateAlert(kind, url.slice(0, 120));
  var spa = redirectTargetUrl(gc, lockedPageUrlForBlocked(url));
  if (spa && spa.indexOf("locked.html") >= 0) {
    var next = (gc.morning && gc.morning.next) || "";
    var mode = String((gc.browser && gc.browser.mode) || "").toLowerCase();
    if (next === "bible" || mode === "bible") {
      spa = (gc.browser && gc.browser.bible_url) || CALT_BIBLE_URL;
    } else if (next === "plan" || mode === "planning") {
      spa = (gc.browser && gc.browser.plan_url) || CALT_PRODUCTIVITY_URL;
    } else {
      spa = lockedPageUrlForBlocked(url);
    }
  } else if (!spa) {
    spa = lockedPageUrlForBlocked(url);
  }
  return softLandBlockedTab(tabId, spa);
}

if (extAPI.webNavigation && extAPI.webNavigation.onCommitted) {
  extAPI.webNavigation.onCommitted.addListener(function (details) {
    if (details.frameId !== 0) return;
    if (!details.url || !details.tabId) return;
    void maybeRedirectTab(details.tabId, details.url, "");
  });
}

if (extAPI.tabs && extAPI.tabs.onRemoved) {
  extAPI.tabs.onRemoved.addListener(function (tabId) {
    delete softLandDone[tabId];
    delete softLandInFlight[tabId];
  });
}

function pruneAndLoadTempAllows(cb) {
  extAPI.storage.local.get([TEMP_ALLOW_STORAGE_KEY || "tempAllows"], function (res) {
    var list = Array.isArray(res.tempAllows) ? res.tempAllows : [];
    list = typeof pruneTempAllows === "function" ? pruneTempAllows(list, Date.now()) : list;
    cb(list);
  });
}

extAPI.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
  if (!msg || !msg.type) return false;
  if (msg.type === "CONTENT_SCORE_WARN") {
    return false;
  }
  if (msg.type === "CONTENT_SCORE_LOCK") {
    if (!redirectsEnabled) {
      sendResponse({ ok: false });
      return false;
    }
    var lockUrl = String(msg.url || "");
    var tabId = sender && sender.tab && sender.tab.id;
    reportGateAlert(
      "distraction",
      "content_score:" + String(msg.score || 0) + " " + lockUrl.slice(0, 100)
    );
    if (typeof tabId === "number") {
      void softLand(tabId, lockedPageUrlForBlocked(lockUrl));
    }
    sendResponse({ ok: true });
    return false;
  }
  if (msg.type === "GET_GATE") {
    sendResponse({ gateCache: gateCache, redirectsEnabled: redirectsEnabled });
    return false;
  }
  if (msg.type === "REFRESH_GATE") {
    void pollGate().then(function () {
      sendResponse({ ok: true, gateCache: gateCache });
    });
    return true;
  }
  if (msg.type === "SET_REDIRECTS") {
    redirectsEnabled = Boolean(msg.enabled);
    extAPI.storage.local.set({ redirectsEnabled: redirectsEnabled });
    void syncDeclarativeWatchBlock({ force: true });
    void syncDeclarativePornBlock({ force: true });
    sendResponse({ ok: true, redirectsEnabled: redirectsEnabled });
    return false;
  }
  if (msg.type === "TEMP_ALLOW_STATUS") {
    var hostS = String(msg.host || "")
      .toLowerCase()
      .replace(/^www\./, "");
    pruneAndLoadTempAllows(function (list) {
      var polS = typeof browserPolicyOrFallback === "function" ? browserPolicyOrFallback(gateCache && gateCache.browser) : {};
      var excludedS = !hostS || (typeof isTempAllowExcludedHost === "function" && isTempAllowExcludedHost(hostS, polS));
      var untilS =
        typeof tempAllowUntilForHost === "function" ? tempAllowUntilForHost(hostS, list, Date.now()) : 0;
      sendResponse({
        ok: true,
        host: hostS,
        excluded: excludedS,
        can_allow: Boolean(hostS) && !excludedS,
        allowed_until: untilS || 0,
        temp_allow_ms: typeof TEMP_ALLOW_MS !== "undefined" ? TEMP_ALLOW_MS : 60000,
        temp_allows: list,
      });
    });
    return true;
  }
  if (msg.type === "TEMP_ALLOW_REQUEST") {
    var hostR = String(msg.host || "")
      .toLowerCase()
      .replace(/^www\./, "");
    var nowR = Date.now();
    var polR = typeof browserPolicyOrFallback === "function" ? browserPolicyOrFallback(gateCache && gateCache.browser) : {};
    var grant = typeof buildTempAllowGrant === "function" ? buildTempAllowGrant(hostR, nowR, polR) : { ok: false };
    if (!grant.ok) {
      sendResponse({
        ok: false,
        error: (grant && grant.error) || "This site can't be temporarily allowed",
        host: hostR,
      });
      return false;
    }
    pruneAndLoadTempAllows(function (list) {
      list = typeof upsertTempAllow === "function" ? upsertTempAllow(list, grant.entry, nowR) : list.concat([grant.entry]);
      tempAllowsCache = list;
      var key = TEMP_ALLOW_STORAGE_KEY || "tempAllows";
      var payload = {};
      payload[key] = list;
      payload.tempAllows = list;
      extAPI.storage.local.set(payload, function () {
        sendResponse({
          ok: true,
          host: grant.entry.host,
          until: grant.entry.until,
          temp_allow_ms: typeof TEMP_ALLOW_MS !== "undefined" ? TEMP_ALLOW_MS : 60000,
        });
      });
    });
    return true;
  }
  return false;
});
