/**
 * Points users at Settings → Overview (live SoftLand / Arm) + native enforcer.
 */
export function DesktopManagedBanner({ feature }: { feature: string }) {
  return (
    <div className="rounded-xl border border-teal-500/30 bg-teal-500/10 px-3 py-3 text-xs leading-relaxed text-teal-100/95 space-y-2">
      <p>
        <span className="font-medium text-foreground">{feature}</span> — SoftLand + Arm live in{" "}
        <a
          href="/productivity?tab=settings&section=overview"
          className="text-foreground underline underline-offset-2"
        >
          Settings → Overview
        </a>
        , not a Python desktop app.
      </p>
      <ul className="list-disc pl-4 space-y-1 text-muted-foreground">
        <li>
          <span className="text-foreground">Overview</span> — what’s blocked, why, until; earned free
          time; Arm / Disarm
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
        <code className="text-[10px] text-foreground">
          /productivity?tab=settings&section=overview
        </code>
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
