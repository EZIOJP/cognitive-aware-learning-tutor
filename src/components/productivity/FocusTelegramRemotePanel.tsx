import { useCallback, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import {
  isTelegramRemoteBridgeAvailable,
  telegramRemoteCmd,
  type TelegramRemoteStatus,
} from "../../lib/focusTelegramRemote";

/**
 * Settings → Advanced: Telegram bot remote (status / SoftLand / PC power).
 * SoftLand ≠ Arm; Arm hard-block is not exposed on Telegram v1.
 */
export function FocusTelegramRemotePanel() {
  const focusShell = isFocusDesktopShell();
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [status, setStatus] = useState<TelegramRemoteStatus | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [token, setToken] = useState("");
  const [allowChat, setAllowChat] = useState(true);
  const [allowPower, setAllowPower] = useState(true);

  const refresh = useCallback(async () => {
    if (!isTelegramRemoteBridgeAvailable()) {
      setHint("Open Focus desktop (calt_focus) to enable Telegram remote.");
      return;
    }
    const r = await telegramRemoteCmd("status");
    setStatus(r);
    if (r) {
      setEnabled(Boolean(r.enabled));
      setAllowChat(r.allow_chat !== false);
      setAllowPower(r.allow_power !== false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const save = async (extra?: { link_next?: boolean; start?: boolean; stop?: boolean }) => {
    if (!focusShell || !isTelegramRemoteBridgeAvailable()) {
      setHint("Telegram remote needs Focus desktop.");
      return;
    }
    setBusy(true);
    setHint(null);
    try {
      const fields = {
        enabled: extra?.stop ? false : extra?.start ? true : enabled,
        allow_chat: allowChat,
        allow_power: allowPower,
        link_next: Boolean(extra?.link_next),
        ...(token.trim() ? { bot_token: token.trim() } : {}),
      };
      let op: "save" | "start" | "stop" | "link_next" = "save";
      if (extra?.link_next) op = "link_next";
      else if (extra?.start) op = "start";
      else if (extra?.stop) op = "stop";
      const r = await telegramRemoteCmd(op, fields);
      setStatus(r);
      setToken("");
      if (r?.ok === false) {
        setHint(r.error || r.last_error || "Save failed");
      } else if (extra?.link_next) {
        setHint("Link armed — open your bot in Telegram and send /start or link.");
      } else if (r?.enabled && r?.polling) {
        setHint("Telegram remote polling.");
      } else if (r?.enabled) {
        setHint("Saved — polling should start in a moment. Refresh status.");
      } else {
        setHint("Saved (disabled).");
      }
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-white/90">Telegram remote</h4>
          <p className="text-[11px] text-white/45 mt-0.5 leading-relaxed">
            Message Focus from your phone (home or away). Commands: status, softland, pass, lock,
            sleep, shutdown CONFIRM. SoftLand ≠ Arm — Arm is not remote.
          </p>
        </div>
        {busy ? <Loader2 className="h-4 w-4 animate-spin text-white/40 shrink-0" /> : null}
      </div>

      {!focusShell ? (
        <p className="text-xs text-amber-200/80">Available only inside calt_focus WebView.</p>
      ) : (
        <>
          <label className="flex items-center gap-2 text-xs text-white/80">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="rounded border-white/20"
            />
            Enable bot
          </label>

          <div className="space-y-1">
            <label className="text-[10px] uppercase tracking-wide text-white/40">Bot token</label>
            <input
              type="password"
              autoComplete="off"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder={
                status?.has_token
                  ? `Saved ${status.bot_token_masked || "****"} — paste to replace`
                  : "123456:ABC… from @BotFather"
              }
              className="w-full rounded-md border border-white/15 bg-zinc-900 px-2 py-1.5 text-xs text-zinc-100 placeholder:text-zinc-500"
            />
          </div>

          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-xs text-white/70">
              <input
                type="checkbox"
                checked={allowChat}
                onChange={(e) => setAllowChat(e.target.checked)}
                className="rounded border-white/20"
              />
              Free chat (OpenJarvis)
            </label>
            <label className="flex items-center gap-2 text-xs text-white/70">
              <input
                type="checkbox"
                checked={allowPower}
                onChange={(e) => setAllowPower(e.target.checked)}
                className="rounded border-white/20"
              />
              Power (lock / sleep / shutdown)
            </label>
          </div>

          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              disabled={busy}
              onClick={() => void save()}
              className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void save({ start: true })}
              className="rounded-lg bg-emerald-700/80 px-3 py-1.5 text-xs text-white hover:bg-emerald-600 disabled:opacity-50"
            >
              Save & start
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void save({ stop: true })}
              className="rounded-lg bg-white/10 px-3 py-1.5 text-xs text-white/70 hover:bg-white/15 disabled:opacity-50"
            >
              Stop
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void save({ link_next: true, start: true })}
              className="rounded-lg bg-amber-700/70 px-3 py-1.5 text-xs text-white hover:bg-amber-600 disabled:opacity-50"
            >
              Allow next chat
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void refresh()}
              className="rounded-lg bg-white/10 px-3 py-1.5 text-xs text-white/60 hover:bg-white/15 disabled:opacity-50"
            >
              Refresh
            </button>
          </div>

          <div className="text-[11px] text-white/45 space-y-1 font-mono">
            <div>
              Status: {status?.polling ? "polling" : status?.enabled ? "enabled" : "off"}
              {status?.last_error ? ` · err ${status.last_error}` : ""}
            </div>
            <div>
              Chats:{" "}
              {(status?.allowed_chat_ids || []).length
                ? (status?.allowed_chat_ids || []).join(", ")
                : "(none — use Allow next chat)"}
            </div>
            {status?.link_next ? (
              <div className="text-amber-200/80">Waiting for /start or link from Telegram…</div>
            ) : null}
          </div>
        </>
      )}

      {hint ? <p className="text-xs text-emerald-200/80">{hint}</p> : null}
    </div>
  );
}

export default FocusTelegramRemotePanel;
