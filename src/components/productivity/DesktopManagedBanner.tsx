/**
 * Points users at live SoftLand / Arm surfaces (new Settings IA).
 */
export function DesktopManagedBanner({ feature }: { feature: string }) {
  return (
    <div className="rounded-xl border border-teal-500/30 bg-teal-500/10 px-3 py-3 text-xs leading-relaxed text-teal-100/95 space-y-2">
      <p>
        <span className="font-medium text-foreground">{feature}</span> — SoftLand + Arm live in Focus
        Settings, not a Python desktop app.
      </p>
      <ul className="list-disc pl-4 space-y-1 text-muted-foreground">
        <li>
          <span className="text-foreground">Overview</span> — what’s on (Site block · Arm · enforcer)
        </li>
        <li>
          <span className="text-foreground">Blocks</span> — site lists, app kill list, device hosts
        </li>
        <li>
          <span className="text-foreground">Unlock</span> — daily goal, reward/pass, Arm / Disarm
        </li>
        <li>
          <span className="text-foreground">Edge CALT Gate</span> — browser SoftLand
        </li>
      </ul>
      <p className="text-muted-foreground">
        <a
          href="/productivity?tab=settings&section=overview"
          className="text-foreground underline underline-offset-2"
        >
          Settings → Overview
        </a>
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
