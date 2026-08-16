import { LayoutGrid, Maximize2, Minimize2, Plus } from "lucide-react";
import { useLocation } from "react-router";
import { useDashboardChromeOptional } from "../../context/DashboardChromeContext";

/** Combined Focus / Add Widget / Customize — only on dashboard when HomePage is mounted. */
export function DashboardChromeDock() {
  const { pathname } = useLocation();
  const chrome = useDashboardChromeOptional();
  const actions = chrome?.actions;

  if (pathname !== "/" || !actions) return null;

  const seg =
    "inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium transition-colors " +
    "hover:bg-white/8 hover:text-primary first:rounded-l-[0.65rem] last:rounded-r-[0.65rem]";

  return (
    <div
      className="gloss-dock-btn inline-flex items-stretch rounded-xl p-0.5 border border-border/50"
      role="group"
      aria-label="Dashboard layout"
    >
      <button
        type="button"
        onClick={actions.toggleFocus}
        className={`${seg} ${
          actions.focusMode ? "bg-primary/15 text-primary" : "text-foreground"
        }`}
        title="Focus mode — life clock and study time only"
      >
        {actions.focusMode ? (
          <Minimize2 className="w-3.5 h-3.5" />
        ) : (
          <Maximize2 className="w-3.5 h-3.5" />
        )}
        <span className="hidden sm:inline">Focus</span>
      </button>
      <span className="w-px self-stretch bg-border/60 my-1" aria-hidden />
      <button
        type="button"
        onClick={actions.openAddWidget}
        className={`${seg} text-foreground`}
        title="Add widgets to dashboard"
      >
        <Plus className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">Add</span>
      </button>
      <span className="w-px self-stretch bg-border/60 my-1" aria-hidden />
      <button
        id="dashboard-customize-btn"
        type="button"
        onClick={actions.openCustomize}
        className={`${seg} text-foreground`}
        title="Customize dashboard layout"
      >
        <LayoutGrid className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">Customize</span>
      </button>
    </div>
  );
}
