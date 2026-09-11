import { ExternalLink, Monitor } from "lucide-react";
import { Link } from "react-router";

type Props = {
  title?: string;
  body?: string;
  deepHash?: string;
};

/**
 * Study-browser gate: life/productivity features live in calt_focus.
 */
export function OpenFocusInterstitial({
  title = "This lives in CALT Focus",
  body = "Bible, Journal, Calendar, Plan, SoftLand, and Arm are controlled from the desktop Focus app (calt_focus.exe), not this Study browser window.",
  deepHash = "/productivity",
}: Props) {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center gap-6 px-6 py-16 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-border/60 bg-card/80">
        <Monitor className="h-7 w-7 text-foreground/80" aria-hidden />
      </div>
      <div className="space-y-2">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {body} Open Focus from the system tray, or run{" "}
          <code className="text-xs">scripts\desktop_tracker\run\run_calt_desktop.bat</code>.
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link
          to="/"
          className="inline-flex items-center gap-2 rounded-xl border border-border/60 bg-background px-4 py-2 text-sm text-foreground hover:bg-muted/40"
        >
          Back to Study home
        </Link>
        <a
          className="inline-flex items-center gap-2 rounded-xl border border-sky-500/30 bg-sky-500/10 px-4 py-2 text-sm text-sky-200 hover:bg-sky-500/15"
          href={`https://calt.app/index.html#${deepHash}`}
          title="Only works inside calt_focus WebView2"
        >
          <ExternalLink className="h-3.5 w-3.5" aria-hidden />
          Focus deep link
        </a>
      </div>
    </div>
  );
}

export default OpenFocusInterstitial;
