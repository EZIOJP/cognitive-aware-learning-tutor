/**
 * Resolve API / WebSocket URLs for localhost vs LAN (phone/tablet on same WiFi).
 *
 * Override in .env:
 *   VITE_API_URL=http://192.168.1.10:8000
 *   VITE_VOCAB_API_BASE=http://192.168.1.10:8000/api/vocab
 *   VITE_WS_URL=ws://192.168.1.10:8000/ws/eeg
 */
function hostFromWindow(): string | null {
  if (typeof window === "undefined") return null;
  const host = window.location.hostname;
  if (host && host !== "localhost" && host !== "127.0.0.1") return host;
  return null;
}

function lanHost(): string {
  return hostFromWindow() ?? "localhost";
}

export function resolveApiUrl(): string {
  const legacy = import.meta.env.VITE_API_BASE;
  if (typeof legacy === "string" && legacy.trim()) {
    return legacy.trim().replace(/\/$/, "");
  }
  const env = import.meta.env.VITE_API_URL;
  if (typeof env === "string" && env.trim()) {
    return env.trim().replace(/\/$/, "");
  }
  return `http://${lanHost()}:8000`;
}

export function resolveVocabApiUrl(): string {
  const env = import.meta.env.VITE_VOCAB_API_BASE;
  if (typeof env === "string" && env.trim()) {
    return env.trim().replace(/\/$/, "");
  }
  return `${resolveApiUrl()}/api/vocab`;
}

/** WebSocket URL for a path on the API host (default path: /ws/eeg). */
export function resolveWsUrl(path = "/ws/eeg"): string {
  const env = import.meta.env.VITE_WS_URL;
  if (typeof env === "string" && env.trim() && path === "/ws/eeg") {
    return env.trim();
  }
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const api = resolveApiUrl().replace(/^http/, "ws");
  try {
    const u = new URL(api);
    return `ws://${u.host}${normalized}`;
  } catch {
    return `ws://${lanHost()}:8000${normalized}`;
  }
}

export function resolveWebSocketUrl(): string {
  return resolveWsUrl("/ws/eeg");
}

export function resolveNutritionWsUrl(): string {
  return resolveWsUrl("/ws/nutrition/live");
}
