/**
 * Optional CALT Sync setup hint. Prefer ZeppBridge pull in Focus;
 * :8765 hub is legacy when Bridge is unavailable.
 */
export function WatchPcHubBanner() {
  return (
    <div className="rounded-xl border border-sky-500/25 bg-sky-500/10 px-3 py-3 text-xs leading-relaxed text-sky-50/95 space-y-2">
      <p>
        <span className="font-medium text-foreground">Wearables path.</span> Prefer{" "}
        <span className="text-foreground">ZeppBridge</span> pull on the PC (Settings → Wearables).
        CALT Sync on port <code className="text-[11px] text-foreground">8765</code> is optional when
        Bridge is unavailable — not a Study API dependency.
      </p>
      <ul className="list-disc pl-4 space-y-1 text-muted-foreground">
        <li>
          Hub URL — <code className="text-foreground">http://&lt;PC-LAN-IP&gt;:8765</code> (never
          localhost on the phone)
        </li>
        <li>
          Token — <code className="text-foreground">calt-local-wearables</code>
        </li>
      </ul>
      <p className="text-muted-foreground">
        Sideload after updates:{" "}
        <code className="text-[10px]">packages\calt-zepp\sideload.bat</code> ·{" "}
        <code className="text-[10px]">packages\calt-voice\sideload.bat</code>.
      </p>
    </div>
  );
}

export default WatchPcHubBanner;
