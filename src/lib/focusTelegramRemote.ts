/**
 * Native Telegram remote bridge (calt_focus long-poll).
 */

export type TelegramRemoteStatus = {
  ok?: boolean;
  id?: string;
  op?: string;
  enabled?: boolean;
  polling?: boolean;
  bot_token_masked?: string;
  has_token?: boolean;
  allow_chat?: boolean;
  allow_power?: boolean;
  link_next?: boolean;
  allowed_chat_ids?: number[];
  last_error?: string;
  error?: string;
  type?: string;
};

export type TelegramRemoteSaveFields = {
  enabled?: boolean;
  bot_token?: string;
  allow_chat?: boolean;
  allow_power?: boolean;
  link_next?: boolean;
  chat_ids?: string;
};

function hasWebViewBridge(): boolean {
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void } };
  };
  return Boolean(w.chrome?.webview?.postMessage);
}

export function isTelegramRemoteBridgeAvailable(): boolean {
  return hasWebViewBridge();
}

export async function telegramRemoteCmd(
  op: "status" | "save" | "start" | "stop" | "link_next",
  fields: TelegramRemoteSaveFields = {},
  timeoutMs = 20000,
): Promise<TelegramRemoteStatus | null> {
  if (!hasWebViewBridge()) return null;
  const w = window as Window & {
    chrome: {
      webview: {
        postMessage: (m: unknown) => void;
        addEventListener: (type: string, fn: (e: MessageEvent) => void) => void;
        removeEventListener: (type: string, fn: (e: MessageEvent) => void) => void;
      };
    };
  };
  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `tg-${Date.now()}`;

  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      cleanup();
      resolve({ ok: false, id, op, error: "timeout" });
    }, timeoutMs);

    const onMsg = (e: MessageEvent) => {
      let data: TelegramRemoteStatus | null = null;
      try {
        data = typeof e.data === "string" ? JSON.parse(e.data) : (e.data as TelegramRemoteStatus);
      } catch {
        return;
      }
      if (!data || data.type !== "telegram_remote_result" || data.id !== id) return;
      cleanup();
      resolve(data);
    };

    const cleanup = () => {
      window.clearTimeout(timer);
      w.chrome.webview.removeEventListener("message", onMsg);
    };

    w.chrome.webview.addEventListener("message", onMsg);
    try {
      w.chrome.webview.postMessage({
        type: "telegram_remote",
        v: 1,
        id,
        op,
        ...fields,
      });
    } catch {
      cleanup();
      resolve(null);
    }
  });
}
