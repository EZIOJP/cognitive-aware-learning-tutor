// ============================================================
// SelfTracker — background.js
// Tracks tab switches, active time, and manages data storage
// ============================================================

let activeTabId = null;
let activeUrl = null;
let activeTitle = null;
let sessionStart = Date.now();
let tabSwitchCount = 0;
let dailyLog = [];

// ── Load existing log from storage on startup ──────────────
chrome.storage.local.get(['dailyLog', 'tabSwitchCount'], (result) => {
  if (result.dailyLog) dailyLog = result.dailyLog;
  if (result.tabSwitchCount) tabSwitchCount = result.tabSwitchCount;
});

// ── Establish Reconnecting WebSocket to FastAPI ──────────────────
let ws = null;
let wsRetryTimeout = null;

function connectWebSocket() {
  try {
    ws = new WebSocket('ws://localhost:8000/ws/behavior');

    ws.onopen = () => {
      console.log('🔌 SelfTracker: Connected to AI Core backend');
      if (wsRetryTimeout) { clearTimeout(wsRetryTimeout); wsRetryTimeout = null; }
    };

    ws.onclose = () => {
      console.log('🔌 SelfTracker: Disconnected from backend. Retrying in 5s...');
      ws = null;
      wsRetryTimeout = setTimeout(connectWebSocket, 5000);
    };

    ws.onerror = () => {
      // Silently swallow — onclose handles reconnect
      ws = null;
    };
  } catch (e) {
    console.warn('SelfTracker: WebSocket unavailable. Running in offline mode.');
    wsRetryTimeout = setTimeout(connectWebSocket, 10000);
  }
}

// Delay initial connect by 2s to let the service worker settle
setTimeout(connectWebSocket, 2000);

// ── Helper: classify URL into a category ──────────────────
function classifyUrl(url, title) {
  if (!url) return 'Unknown';
  const u = url.toLowerCase();

  if (u.includes('github') || u.includes('gitlab') || u.includes('stackoverflow') || u.includes('docs.') || u.includes('developer.') || u.includes('mdn')) return 'Dev / Docs';
  if (u.includes('notion') || u.includes('obsidian') || u.includes('roamresearch') || u.includes('logseq')) return 'Knowledge Work';
  if (u.includes('figma') || u.includes('canva') || u.includes('excalidraw')) return 'Design';
  if (u.includes('mail') || u.includes('gmail') || u.includes('outlook') || u.includes('calendar')) return 'Admin / Email';
  if (u.includes('meet.google') || u.includes('zoom') || u.includes('teams.microsoft') || u.includes('discord')) return 'Communication';
  if (u.includes('coursera') || u.includes('udemy') || u.includes('edx') || u.includes('khanacademy') || u.includes('leetcode') || u.includes('brilliant') || u.includes('scaler.com')) return 'Coursework';
  if (u.includes('wikipedia') || u.includes('arxiv') || u.includes('scholar.google') || u.includes('pubmed') || u.includes('jstor')) return 'Research';
  if (u.includes('youtube') || u.includes('twitch') || u.includes('netflix') || u.includes('primevideo') || u.includes('disneyplus')) return 'Video / Streaming';
  if (u.includes('reddit') || u.includes('twitter') || u.includes('x.com') || u.includes('instagram') || u.includes('tiktok') || u.includes('facebook') || u.includes('linkedin')) return 'Social Media';
  if (u.includes('chess') || u.includes('steam') || u.includes('game') || u.includes('itch.io') || u.includes('kongregate')) return 'Gaming';
  if (u.includes('spotify') || u.includes('soundcloud') || u.includes('music')) return 'Music';
  if (u.includes('news') || u.includes('bbc') || u.includes('cnn') || u.includes('theguardian')) return 'News';
  if (u.includes('amazon') || u.includes('flipkart') || u.includes('myntra') || u.includes('ebay')) return 'Shopping';
  if (u === 'chrome://newtab/' || u === 'about:blank' || u === '') return 'Idle / New Tab';

  return 'Browsing';
}

// ── Helper: determine productivity score (0–100) ──────────
function productivityScore(category) {
  const scores = {
    'Dev / Docs': 95, 'Research': 90, 'Coursework': 88, 'Knowledge Work': 85,
    'Design': 80, 'Admin / Email': 55, 'Communication': 50, 'News': 35,
    'Browsing': 30, 'Music': 25, 'Shopping': 20, 'Social Media': 10,
    'Video / Streaming': 10, 'Gaming': 15, 'Idle / New Tab': 0, 'Unknown': 0
  };
  return scores[category] ?? 30;
}

// ── Log current session before switching ──────────────────
function logCurrentSession(reason = 'tab_switch') {
  if (!activeUrl || activeUrl.startsWith('chrome://')) return;

  const duration = Math.round((Date.now() - sessionStart) / 1000);
  if (duration < 2) return;

  const category = classifyUrl(activeUrl, activeTitle);
  const entry = {
    timestamp: sessionStart,
    end_timestamp: Date.now(),
    duration_seconds: duration,
    url: activeUrl,
    title: activeTitle || 'Untitled',
    domain: extractDomain(activeUrl),
    category,
    productivity_score: productivityScore(category),
    reason,
    tab_switches_today: tabSwitchCount
  };

  dailyLog.push(entry);
  if (dailyLog.length > 5000) dailyLog = dailyLog.slice(-5000);
  chrome.storage.local.set({ dailyLog, lastEntry: entry, tabSwitchCount });

  // Stream completed session entry to FastAPI
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'SESSION_END', ...entry }));
  }
}

function extractDomain(url) {
  try {
    return new URL(url).hostname.replace('www.', '');
  } catch {
    return 'unknown';
  }
}

// ── Tab activated ─────────────────────────────────────────
chrome.tabs.onActivated.addListener(async (info) => {
  logCurrentSession('tab_switch');
  tabSwitchCount++;

  try {
    const tab = await chrome.tabs.get(info.tabId);
    activeTabId = info.tabId;
    activeUrl = tab.url;
    activeTitle = tab.title;
    sessionStart = Date.now();
  } catch (e) {}
});

// ── Tab updated (URL change within same tab) ──────────────
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (tabId !== activeTabId) return;
  if (changeInfo.status !== 'complete') return;

  logCurrentSession('navigation');
  activeUrl = tab.url;
  activeTitle = tab.title;
  sessionStart = Date.now();
});

// ── Window focus changed ──────────────────────────────────
chrome.windows.onFocusChanged.addListener((windowId) => {
  if (windowId === chrome.windows.WINDOW_ID_NONE) {
    logCurrentSession('window_blur');
  } else {
    sessionStart = Date.now();
  }
});

// ── Idle detection ────────────────────────────────────────
chrome.idle.setDetectionInterval(60);
chrome.idle.onStateChanged.addListener((state) => {
  if (state === 'idle' || state === 'locked') {
    logCurrentSession('idle');
  } else if (state === 'active') {
    sessionStart = Date.now();
  }
});

// ── Periodic flush every 30 seconds ──────────────────────
chrome.alarms.create('flush', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'flush') {
    if (activeUrl && !activeUrl.startsWith('chrome://')) {
      const category = classifyUrl(activeUrl, activeTitle);
      const liveEntry = {
        timestamp: sessionStart,
        end_timestamp: Date.now(),
        duration_seconds: Math.round((Date.now() - sessionStart) / 1000),
        url: activeUrl,
        title: activeTitle || 'Untitled',
        domain: extractDomain(activeUrl),
        category,
        productivity_score: productivityScore(category),
        reason: 'live',
        tab_switches_today: tabSwitchCount
      };
      chrome.storage.local.set({ liveEntry });

      // Stream the live heartbeat snapshot to FastAPI
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'LIVE_SNAPSHOT', ...liveEntry }));
      }
    }
  }
});

// ── Message from content script (behavioral data) ─────────
chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg.type === 'BEHAVIORAL_UPDATE') {
    const rawPayload = {
      type: 'BEHAVIORAL_UPDATE',
      timestamp: Date.now(),
      url: sender.tab?.url || '',
      domain: sender.tab?.url ? extractDomain(sender.tab.url) : '',
      ...msg.data
    };

    // 1. Keep existing local storage backup
    chrome.storage.local.get(['behavioralLog'], (result) => {
      const log = result.behavioralLog || [];
      log.push(rawPayload);
      if (log.length > 2000) log.splice(0, log.length - 2000);
      chrome.storage.local.set({ behavioralLog: log });
    });

    // 2. Stream to FastAPI if connected
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(rawPayload));
    }
  }

  if (msg.type === 'GET_STATS') {
    chrome.storage.local.get(['dailyLog', 'behavioralLog', 'tabSwitchCount', 'liveEntry'], (result) => {
      chrome.runtime.sendMessage({ type: 'STATS_RESPONSE', data: result });
    });
  }

  if (msg.type === 'EXPORT_CSV') {
    chrome.storage.local.get(['dailyLog'], (result) => {
      chrome.runtime.sendMessage({ type: 'CSV_READY', data: result.dailyLog || [] });
    });
  }

  if (msg.type === 'CLEAR_DATA') {
    dailyLog = [];
    tabSwitchCount = 0;
    chrome.storage.local.set({ dailyLog: [], behavioralLog: [], tabSwitchCount: 0, liveEntry: null });
  }
});
