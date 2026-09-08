import { useEffect, useRef, useState } from "react";
import { Activity, Radio, WifiOff } from "lucide-react";
import { Card } from "../../app/components/ui/card";
import { resolveApiUrl } from "../../utils/resolveBackendUrl";

type EegStatus = {
  enabled: boolean;
  status: string;
  packet_count: number;
  snap_count: number;
  last_voltage: number | null;
  last_from: string | null;
  last_packet_age_s: number | null;
  last_snap_age_s: number | null;
  ok: boolean;
};

type SnapEvent = { id: number; at: string; voltage: number };

/**
 * Live ESP32 SELF_TEST snap detector — polls /api/eeg/status.
 * Requires EEG_ENABLED=1 on the API and board UDP → this PC.
 */
export function Esp32SnapCheck() {
  const [st, setSt] = useState<EegStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [snaps, setSnaps] = useState<SnapEvent[]>([]);
  const [flash, setFlash] = useState(false);
  const lastCount = useRef(0);
  const idRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await fetch(resolveApiUrl("/api/eeg/status"));
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as EegStatus;
        if (cancelled) return;
        setError(null);
        setSt(data);
        if (data.snap_count > lastCount.current) {
          const v = data.last_voltage ?? 0;
          idRef.current += 1;
          setSnaps((prev) =>
            [
              {
                id: idRef.current,
                at: new Date().toLocaleTimeString(),
                voltage: v,
              },
              ...prev,
            ].slice(0, 12),
          );
          setFlash(true);
          window.setTimeout(() => setFlash(false), 600);
        }
        lastCount.current = data.snap_count;
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "API unreachable");
        }
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 400);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const live =
    st?.enabled &&
    (st.status === "streaming" || st.status === "warming") &&
    (st.last_packet_age_s == null || st.last_packet_age_s < 3);

  return (
    <Card
      className={`p-5 gloss-panel border-white/10 space-y-3 transition-colors ${
        flash ? "border-emerald-400/60 bg-emerald-500/10" : ""
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-cyan-500/15 flex items-center justify-center shrink-0">
          <Radio className="w-5 h-5 text-cyan-400" />
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-semibold text-foreground text-sm">ESP32 snap test</p>
          <p className="text-xs text-muted-foreground">
            Board SELF_TEST pulses every ~2s over WiFi → UDP :5005. Watch the counter tick.
          </p>
        </div>
      </div>

      {error && (
        <p className="text-xs text-destructive">API: {error} — is the backend running?</p>
      )}

      {!st?.enabled && !error && (
        <p className="text-xs text-amber-400">
          EEG is off on the server. Set <code className="text-[10px]">EEG_ENABLED=1</code> in{" "}
          <code className="text-[10px]">.env</code> and restart the API.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span
          className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium ${
            live
              ? "bg-emerald-500/20 text-emerald-300"
              : "bg-muted text-muted-foreground"
          }`}
        >
          {live ? <Activity className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
          {st?.enabled ? st.status : "disabled"}
        </span>
        <span className="font-mono text-lg font-semibold text-foreground">
          SNAP #{st?.snap_count ?? 0}
        </span>
        <span className="font-mono text-xs text-muted-foreground">
          {st?.last_voltage != null ? `${st.last_voltage.toFixed(3)} V` : "— V"}
        </span>
        <span className="text-[10px] text-muted-foreground">
          packets {st?.packet_count ?? 0}
          {st?.last_from ? ` · from ${st.last_from}` : ""}
        </span>
      </div>

      <div className="h-2 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full bg-cyan-500/80 transition-all duration-150"
          style={{
            width: `${Math.min(100, ((st?.last_voltage ?? 1.65) - 1.2) / 1.8 * 100)}%`,
          }}
        />
      </div>

      {snaps.length > 0 ? (
        <ul className="max-h-28 overflow-auto space-y-1 text-[11px] font-mono text-muted-foreground">
          {snaps.map((s) => (
            <li key={s.id}>
              #{s.id} · {s.at} · {s.voltage.toFixed(3)}V
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[11px] text-muted-foreground">
          Waiting for first snap… If stuck: board needs 2.4 GHz WiFi, and UDP target must be this PC
          (192.168.0.110).
        </p>
      )}
    </Card>
  );
}
