/**
 * Points users at web Focus + native enforcer (no PySide6 Desktop required).
 * Prefer Settings hub anchors when already on Settings; Focus route remains the tray deep link.
 */
export function DesktopManagedBanner({ feature }: { feature: string }) {
  return (
    <div className="rounded-xl border border-teal-500/30 bg-teal-500/10 px-3 py-3 text-xs leading-relaxed text-teal-100/95 space-y-2">
      <p>
        <span className="font-medium text-foreground">{feature}</span> — SoftLand + Focus live in{" "}
        <a href="#focus" className="text-foreground underline underline-offset-2">
          Settings → Focus
        </a>
        {" "}
        (or{" "}
        <a href="/productivity/focus" className="text-foreground underline underline-offset-2">
          /productivity/focus
        </a>
        ), not a Python desktop app.
      </p>
      <ul className="list-disc pl-4 space-y-1 text-muted-foreground">
        <li>
          <span className="text-foreground">Focus web UI</span> — what’s blocked, why, until;
          incubation + earned free time
        </li>
        <li>
          <span className="text-foreground">Native enforcer (C++)</span> — app hard-block kills
        </li>
        <li>
          <span className="text-foreground">Edge CALT Gate</span> — browser SoftLand (sites)
        </li>
      </ul>
      <p className="text-muted-foreground">
        Open:{" "}
        <code className="text-[10px] text-foreground">/productivity?tab=settings#focus</code>
        {" · "}
        Enforcer:{" "}
        <code className="text-[10px] text-foreground">
          scripts\desktop_tracker\install\install_native_enforcer.ps1
        </code>
      </p>
    </div>
  );
}

export default DesktopManagedBanner;
