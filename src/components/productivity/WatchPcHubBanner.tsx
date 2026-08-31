/**
 * Shared setup for CALT Sync + CALT Voice watch apps.
 * Both post to the desktop tracker hub (:8765); the web app reads results via :8000.
 */
export function WatchPcHubBanner() {
  return (
    <div className="rounded-xl border border-amber-500/25 bg-amber-500/10 px-3 py-3 text-xs leading-relaxed text-amber-100/95 space-y-2">
      <p>
        <span className="font-medium text-foreground">Watch → PC path.</span> Both mini-programs send
        to the <span className="text-foreground">desktop tracker hub</span> on port{" "}
        <code className="text-[11px] text-foreground">8765</code>, not the main API on{" "}
        <code className="text-[11px] text-foreground">8000</code>. Start the desktop tracker, then in
        the phone Zepp app set for <strong>each</strong> app:
      </p>
      <ul className="list-disc pl-4 space-y-1 text-muted-foreground">
        <li>
          Base URL — <code className="text-foreground">http://&lt;PC-LAN-IP&gt;:8765</code> (never
          localhost)
        </li>
        <li>
          Token — <code className="text-foreground">calt-local-wearables</code>
        </li>
      </ul>
      <p className="text-muted-foreground">
        Sideload after updates:{" "}
        <code className="text-[10px]">packages\calt-zepp\sideload.bat</code> ·{" "}
        <code className="text-[10px]">packages\calt-voice\sideload.bat</code>. This page shows data
        once it has landed on the PC.
      </p>
    </div>
  );
}

export default WatchPcHubBanner;
