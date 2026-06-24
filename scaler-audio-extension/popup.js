const urlsEl = document.getElementById("urls");
const statusEl = document.getElementById("status");
const scanBtn = document.getElementById("scan");
const recordBtn = document.getElementById("record");
const stopBtn = document.getElementById("stop");

let pageTitle = "scaler_lecture";

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.style.color = isError ? "#fca5a5" : "#86efac";
}

function shortUrl(url) {
  if (url.length <= 72) return url;
  return url.slice(0, 36) + "…" + url.slice(-28);
}

function renderUrls(urls) {
  urlsEl.innerHTML = "";
  if (!urls.length) {
    urlsEl.innerHTML = "<p style='font-size:11px;color:#86efac99'>No media URLs yet. Start the video, then scan again.</p>";
    return;
  }
  urls.forEach((url) => {
    const row = document.createElement("div");
    row.className = "url-row";
    const label = document.createElement("span");
    label.textContent = shortUrl(url);
    label.style.flex = "1";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Save";
    btn.addEventListener("click", () => downloadUrl(url));
    row.append(label, btn);
    urlsEl.appendChild(row);
  });
}

async function downloadUrl(url) {
  setStatus("Downloading…");
  scanBtn.disabled = true;
  try {
    const resp = await chrome.runtime.sendMessage({ type: "DOWNLOAD_URL", url, title: pageTitle });
    if (resp?.ok) {
      setStatus(`Saved (${resp.method}). Check Downloads/Scaler/`);
    } else {
      setStatus(resp?.error || "Download failed", true);
    }
  } catch (e) {
    setStatus(e?.message || String(e), true);
  } finally {
    scanBtn.disabled = false;
  }
}

scanBtn.addEventListener("click", async () => {
  setStatus("Scanning…");
  scanBtn.disabled = true;
  try {
    const resp = await chrome.runtime.sendMessage({ type: "SCAN_ACTIVE_TAB" });
    if (!resp || resp.error) {
      setStatus(resp?.error || "Scan failed — open a Scaler lecture page.", true);
      return;
    }
    pageTitle = resp.title || pageTitle;
    renderUrls(resp.urls || []);
    const n = (resp.urls || []).length;
    const v = (resp.videos || []).length;
    setStatus(`Found ${n} media URL(s), ${v} video element(s).`);
  } catch (e) {
    setStatus(e?.message || String(e), true);
  } finally {
    scanBtn.disabled = false;
  }
});

recordBtn.addEventListener("click", async () => {
  setStatus("Starting recorder — play the lecture now…");
  recordBtn.disabled = true;
  try {
    const resp = await chrome.runtime.sendMessage({ type: "START_RECORD_TAB" });
    if (resp?.ok) {
      setStatus(resp.message || "Recording…");
      stopBtn.disabled = false;
    } else {
      setStatus(resp?.error || "Record failed", true);
      recordBtn.disabled = false;
    }
  } catch (e) {
    setStatus(e?.message || String(e), true);
    recordBtn.disabled = false;
  }
});

stopBtn.addEventListener("click", async () => {
  setStatus("Stopping…");
  stopBtn.disabled = true;
  try {
    const resp = await chrome.runtime.sendMessage({ type: "STOP_RECORD_TAB" });
    if (resp?.ok) {
      setStatus("Saving recording to Downloads/Scaler/…");
    } else {
      setStatus(resp?.error || "Stop failed", true);
    }
  } catch (e) {
    setStatus(e?.message || String(e), true);
  } finally {
    recordBtn.disabled = false;
    stopBtn.disabled = true;
  }
});

// Auto-scan on open
scanBtn.click();
