import { useCallback, useEffect, useState } from "react";
import { Lightbulb, Usb } from "lucide-react";
import { Card } from "../../app/components/ui/card";
import { resolveApiUrl } from "../../utils/resolveBackendUrl";

type LedAction = "off" | "on" | "slow" | "fast" | "double" | "heartbeat";

type Status = {
  serial_ready?: boolean;
  serial_port?: string | null;
};

const PRIMARY: { action: LedAction; label: string; className: string }[] = [
  { action: "off", label: "Off", className: "bg-muted text-foreground hover:bg-muted/80" },
  { action: "on", label: "On", className: "bg-emerald-600 text-white hover:bg-emerald-500" },
];

const PATTERNS: { action: LedAction; label: string }[] = [
  { action: "slow", label: "Slow blink" },
  { action: "fast", label: "Fast blink" },
  { action: "double", label: "Double" },
  { action: "heartbeat", label: "Heartbeat" },
];

/** System LED on/off + simple blink patterns (USB serial). */
export function Esp32LedPlay() {
  const [st, setSt] = useState<Status | null>(null);
  const [msg, setMsg] = useState("Plug USB → Off / On / pattern");
  const [busy, setBusy] = useState(false);
  const [on, setOn] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(resolveApiUrl("/api/eeg/status"));
      if (!res.ok) return;
      setSt((await res.json()) as Status);
    } catch {
      setSt(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 2000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const send = async (action: LedAction) => {
    setBusy(true);
    setOn(action !== "off");
    try {
      const res = await fetch(resolveApiUrl("/api/eeg/led"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const data = (await res.json()) as { ok?: boolean; error?: string; port?: string };
      if (data.ok) {
        setMsg(`OK · ${action}${data.port ? ` → ${data.port}` : ""}`);
      } else {
        setMsg(data.error ?? "LED command failed");
      }
      void refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "API unreachable — start the backend");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-5 gloss-panel border-white/10 space-y-4">
      <div className="flex items-start gap-3">
        <div
          className={`w-12 h-12 rounded-2xl border border-white/20 shrink-0 transition-colors ${
            on ? "bg-white shadow-[0_0_20px_rgba(255,255,255,0.45)]" : "bg-zinc-800"
          }`}
        />
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-semibold text-foreground text-sm flex items-center gap-2">
            <Lightbulb className="w-4 h-4 text-amber-400" />
            System LED
          </p>
          <p className="text-xs text-muted-foreground">
            On / off the board LED, or run a blink pattern. USB cable required.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span
          className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 font-medium ${
            st?.serial_ready
              ? "bg-emerald-500/20 text-emerald-300"
              : "bg-amber-500/15 text-amber-300"
          }`}
        >
          <Usb className="w-3.5 h-3.5" />
          {st?.serial_ready ? `USB ${st.serial_port}` : "USB not seen — plug the board"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {PRIMARY.map((b) => (
          <button
            key={b.action}
            type="button"
            disabled={busy}
            onClick={() => void send(b.action)}
            className={`rounded-xl px-3 py-3 text-sm font-semibold disabled:opacity-50 ${b.className}`}
          >
            {b.label}
          </button>
        ))}
      </div>

      <div>
        <p className="text-[11px] font-medium text-muted-foreground mb-2">Patterns</p>
        <div className="grid grid-cols-2 gap-2">
          {PATTERNS.map((b) => (
            <button
              key={b.action}
              type="button"
              disabled={busy}
              onClick={() => void send(b.action)}
              className="rounded-xl border border-white/10 bg-background/40 px-3 py-2.5 text-xs font-semibold text-foreground hover:bg-white/10 disabled:opacity-50"
            >
              {b.label}
            </button>
          ))}
        </div>
      </div>

      <p className="text-[11px] font-mono text-muted-foreground">{msg}</p>
    </Card>
  );
}
