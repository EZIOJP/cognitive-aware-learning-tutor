// Scaler Lecture Audio — background service worker

const mediaByTab = new Map();

function safeFilename(title) {
  const base = (title || "scaler_lecture")
    .replace(/[<>:"/\\|?*]/g, "_")
    .replace(/\s+/g, "_")
    .slice(0, 80);
  return base || "scaler_lecture";
}

function resolveUrl(base, relative) {
  try {
    return new URL(relative, base).href;
  } catch {
    return relative;
  }
}

async function fetchText(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return res.text();
}

async function fetchBuffer(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return res.arrayBuffer();
}

function parsePlaylist(text, baseUrl) {
  const lines = text.split("\n").map((l) => l.trim());
  const segments = [];
  let streamUrl = null;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line || line.startsWith("#")) {
      if (line.includes("#EXT-X-STREAM-INF") && lines[i + 1]) {
        streamUrl = resolveUrl(baseUrl, lines[i + 1]);
      }
      continue;
    }
    segments.push(resolveUrl(baseUrl, line));
  }
  return { segments, streamUrl };
}

async function resolveHlsSegments(m3u8Url) {
  const text = await fetchText(m3u8Url);
  let { segments, streamUrl } = parsePlaylist(text, m3u8Url);
  if (!segments.length && streamUrl) {
    const nested = await fetchText(streamUrl);
    ({ segments } = parsePlaylist(nested, streamUrl));
  }
  if (!segments.length) throw new Error("No segments found in HLS playlist.");
  return segments;
}

async function downloadDirect(url, filename) {
  return chrome.downloads.download({
    url,
    filename,
    saveAs: true,
  });
}

async function downloadHlsMerged(m3u8Url, filename) {
  const segments = await resolveHlsSegments(m3u8Url);
  const bufs = [];
  for (const seg of segments) {
    bufs.push(await fetchBuffer(seg));
  }
  const blob = new Blob(bufs, { type: "video/mp2t" });
  const dataUrl = await blobToDataUrl(blob);
  return chrome.downloads.download({
    url: dataUrl,
    filename: filename.endsWith(".ts") ? filename : `${filename}.ts`,
    saveAs: true,
  });
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

async function scanActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("No active tab.");

  let frames = [{ frameId: 0 }];
  try {
    frames = await chrome.webNavigation.getAllFrames({ tabId: tab.id });
  } catch {
    /* main frame only */
  }

  const allUrls = new Set();
  const videos = [];
  for (const frame of frames) {
    try {
      const resp = await chrome.tabs.sendMessage(tab.id, { type: "SCAN_PAGE" }, { frameId: frame.frameId });
      if (resp?.captured) resp.captured.forEach((u) => allUrls.add(u));
      if (resp?.videos) videos.push(...resp.videos.map((v) => ({ ...v, frameId: frame.frameId })));
    } catch {
      /* frame may not have content script */
    }
  }

  const stored = mediaByTab.get(tab.id);
  if (stored?.urls) {
    for (const u of stored.urls) allUrls.add(u);
  }

  mediaByTab.set(tab.id, {
    urls: allUrls,
    title: tab.title || "scaler_lecture",
    pageUrl: tab.url || "",
  });

  return {
    tabId: tab.id,
    title: tab.title || "scaler_lecture",
    pageUrl: tab.url || "",
    urls: [...allUrls],
    videos,
  };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      if (msg.type === "MEDIA_URL") {
        const tabId = sender.tab?.id;
        if (!tabId) return;
        const entry = mediaByTab.get(tabId) || { urls: new Set(), title: "", pageUrl: "" };
        if (!(entry.urls instanceof Set)) entry.urls = new Set(entry.urls || []);
        entry.urls.add(msg.url);
        entry.pageUrl = msg.pageUrl || entry.pageUrl;
        mediaByTab.set(tabId, entry);
        return;
      }

      if (msg.type === "DOWNLOAD_URL") {
        const { url, title } = msg;
        const name = safeFilename(title);
        if (url.toLowerCase().includes(".m3u8")) {
          const id = await downloadHlsMerged(url, `Scaler/${name}_${Date.now()}`);
          sendResponse({ ok: true, downloadId: id, method: "hls" });
        } else {
          const ext = url.includes(".m4a") ? ".m4a" : url.includes(".webm") ? ".webm" : ".mp4";
          const id = await downloadDirect(url, `Scaler/${name}_${Date.now()}${ext}`);
          sendResponse({ ok: true, downloadId: id, method: "direct" });
        }
        return;
      }

      if (msg.type === "RECORDING_BLOB") {
        const ext = msg.mimeType?.includes("ogg") ? ".ogg" : ".webm";
        const name = safeFilename(msg.title);
        const id = await chrome.downloads.download({
          url: msg.dataUrl,
          filename: `Scaler/${name}_${Date.now()}${ext}`,
          saveAs: true,
        });
        sendResponse({ ok: true, downloadId: id, method: "record" });
        return;
      }

      if (msg.type === "SCAN_ACTIVE_TAB") {
        const data = await scanActiveTab();
        sendResponse({ ok: true, ...data });
        return;
      }

      if (msg.type === "START_RECORD_TAB") {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab?.id) {
          sendResponse({ ok: false, error: "No active tab" });
          return;
        }
        const resp = await chrome.tabs.sendMessage(tab.id, { type: "START_RECORD" });
        sendResponse(resp);
        return;
      }

      if (msg.type === "STOP_RECORD_TAB") {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab?.id) {
          sendResponse({ ok: false, error: "No active tab" });
          return;
        }
        const resp = await chrome.tabs.sendMessage(tab.id, { type: "STOP_RECORD" });
        sendResponse(resp);
        return;
      }
    } catch (err) {
      sendResponse({ ok: false, error: err?.message || String(err) });
    }
  })();
  return true;
});
