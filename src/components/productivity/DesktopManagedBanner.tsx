/**
 * Points users at CALT Desktop for rules / watch / voice (calendar stays here).
 */
export function DesktopManagedBanner({ feature }: { feature: string }) {
  return (
    <div className="rounded-xl border border-teal-500/30 bg-teal-500/10 px-3 py-3 text-xs leading-relaxed text-teal-100/95 space-y-2">
      <p>
        <span className="font-medium text-foreground">{feature}</span> is managed in{" "}
        <span className="text-foreground">CALT Desktop</span> (PySide6 tray app), not this page.
      </p>
      <p className="text-muted-foreground">
        Launch: <code className="text-[10px] text-foreground">scripts\desktop_tracker\run_calt_desktop.bat</code>
        {" · "}
        Or: <code className="text-[10px] text-foreground">pythonw -m backend.behavior.calt_desktop</code>
      </p>
      <p className="text-muted-foreground">
        This website keeps the <span className="text-foreground">productivity calendar</span> and study
        stack. Stop the old tracker tray first (single instance).
      </p>
    </div>
  );
}

export default DesktopManagedBanner;
