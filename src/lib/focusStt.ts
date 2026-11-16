/**
 * Focus STT (push-to-talk).
 * Study voice_agent: faster-whisper (Python) → SpeechRecognition fallback.
 * Focus: Web Speech API in Edge WebView2 (no Python SoftLand / faster-whisper process).
 */

export type FocusSttResult = {
  ok: boolean;
  text: string;
  error?: string;
  engine: "web_speech" | "none";
};

type SpeechRec = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((ev: SpeechRecognitionEventLike) => void) | null;
  onerror: ((ev: { error?: string }) => void) | null;
  onend: (() => void) | null;
};

type SpeechRecognitionEventLike = {
  results: ArrayLike<{ 0: { transcript: string }; isFinal?: boolean }>;
};

function getSpeechRecognitionCtor(): (new () => SpeechRec) | null {
  if (typeof window === "undefined") return null;
  const w = window as Window & {
    SpeechRecognition?: new () => SpeechRec;
    webkitSpeechRecognition?: new () => SpeechRec;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function focusSttAvailable(): boolean {
  return Boolean(getSpeechRecognitionCtor());
}

/**
 * Listen once (phrase). Resolves with transcript or error.
 * Default ~8s — matches Study listen_once spirit.
 */
export function listenOnceFocus(opts?: {
  lang?: string;
  timeoutMs?: number;
}): Promise<FocusSttResult> {
  const Ctor = getSpeechRecognitionCtor();
  if (!Ctor) {
    return Promise.resolve({
      ok: false,
      text: "",
      error: "stt_unavailable",
      engine: "none",
    });
  }

  const timeoutMs = opts?.timeoutMs ?? 8000;
  const lang = opts?.lang || "en-IN";

  return new Promise((resolve) => {
    let settled = false;
    const finish = (r: FocusSttResult) => {
      if (settled) return;
      settled = true;
      try {
        rec.abort();
      } catch {
        /* ignore */
      }
      window.clearTimeout(timer);
      resolve(r);
    };

    const rec = new Ctor();
    rec.lang = lang;
    rec.continuous = false;
    rec.interimResults = false;
    rec.maxAlternatives = 1;

    const timer = window.setTimeout(() => {
      finish({ ok: false, text: "", error: "timeout", engine: "web_speech" });
    }, timeoutMs);

    rec.onresult = (ev) => {
      const raw = ev.results?.[0]?.[0]?.transcript || "";
      const text = String(raw).trim();
      if (text) finish({ ok: true, text, engine: "web_speech" });
      else finish({ ok: false, text: "", error: "empty", engine: "web_speech" });
    };
    rec.onerror = (ev) => {
      finish({
        ok: false,
        text: "",
        error: String(ev?.error || "stt_error"),
        engine: "web_speech",
      });
    };
    rec.onend = () => {
      if (!settled) {
        finish({ ok: false, text: "", error: "ended", engine: "web_speech" });
      }
    };

    try {
      rec.start();
    } catch (e) {
      finish({
        ok: false,
        text: "",
        error: e instanceof Error ? e.message : "start_failed",
        engine: "web_speech",
      });
    }
  });
}
