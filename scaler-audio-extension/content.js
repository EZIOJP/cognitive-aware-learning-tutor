// Scaler Lecture Audio — content script (runs in page + iframes)

(function () {
  const captured = new Set();

  function addUrl(url) {
    if (!url || typeof url !== "string") return;
    if (!/^https?:\/\//i.test(url)) return;
    const lower = url.toLowerCase();
    if (
      !lower.includes(".m3u8") &&
      !lower.includes(".mp4") &&
      !lower.includes(".m4a") &&
      !lower.includes(".webm") &&
      !lower.includes(".mpd") &&
      !lower.includes("audio") &&
      !lower.includes("video")
    ) {
      return;
    }
    if (captured.has(url)) return;
    captured.add(url);
    chrome.runtime.sendMessage({ type: "MEDIA_URL", url, pageUrl: location.href }).catch(() => {});
  }

  // Hook fetch / XHR for HLS and MP4 manifests
  const origFetch = window.fetch;
  window.fetch = function (...args) {
    const req = args[0];
    const url = typeof req === "string" ? req : req?.url;
    if (url) addUrl(url);
    return origFetch.apply(this, args);
  };

  const origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    addUrl(String(url));
    return origOpen.call(this, method, url, ...rest);
  };

  function scanVideoElements() {
    const videos = document.querySelectorAll("video");
    const out = [];
    videos.forEach((video, index) => {
      const src = video.currentSrc || video.src || "";
      if (src) addUrl(src);
      const sources = video.querySelectorAll("source");
      sources.forEach((s) => addUrl(s.src));
      out.push({
        index,
        src: src || null,
        duration: Number.isFinite(video.duration) ? video.duration : null,
        title: document.title,
      });
    });
    return out;
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === "SCAN_PAGE") {
      const videos = scanVideoElements();
      sendResponse({
        ok: true,
        videos,
        captured: [...captured],
        title: document.title,
        href: location.href,
      });
      return true;
    }

    if (msg.type === "START_RECORD") {
      startAudioRecord(sendResponse);
      return true;
    }

    if (msg.type === "STOP_RECORD") {
      const rec = window.__scalerAudioRecorder;
      if (rec && rec.state === "recording") {
        rec.stop();
        sendResponse({ ok: true });
      } else {
        sendResponse({ ok: false, error: "No active recording." });
      }
      return true;
    }

    return false;
  });

  async function startAudioRecord(sendResponse) {
    const video = document.querySelector("video");
    if (!video) {
      sendResponse({ ok: false, error: "No <video> found on this page/frame." });
      return;
    }
    try {
      const stream = video.captureStream?.() || video.mozCaptureStream?.();
      if (!stream) {
        sendResponse({ ok: false, error: "captureStream not supported on this player." });
        return;
      }
      const audioTracks = stream.getAudioTracks();
      if (!audioTracks.length) {
        sendResponse({ ok: false, error: "No audio track — try playing the video first." });
        return;
      }
      const audioStream = new MediaStream(audioTracks);
      const recorder = new MediaRecorder(audioStream, { mimeType: pickMime() });
      const chunks = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        const reader = new FileReader();
        reader.onload = () => {
          chrome.runtime.sendMessage({
            type: "RECORDING_BLOB",
            dataUrl: reader.result,
            mimeType: blob.type,
            title: document.title,
          });
        };
        reader.readAsDataURL(blob);
      };

      window.__scalerAudioRecorder = recorder;
      recorder.start(1000);
      if (!video.paused) {
        video.addEventListener(
          "ended",
          () => {
            if (recorder.state === "recording") recorder.stop();
          },
          { once: true },
        );
      }
      sendResponse({
        ok: true,
        message: "Recording audio — play the lecture. Click Stop in the extension when done.",
      });
    } catch (err) {
      sendResponse({ ok: false, error: err?.message || String(err) });
    }
  }

  function pickMime() {
    for (const t of ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "video/webm"]) {
      if (MediaRecorder.isTypeSupported(t)) return t;
    }
    return "";
  }

  scanVideoElements();
})();
