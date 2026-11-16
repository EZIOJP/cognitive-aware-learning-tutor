/**
 * Focus-only sidebar — one glass rail (nav + status + tools).
 * Study shell keeps AppSidebar; Focus never mixes the old 3-piece footer pile.
 */
import {
  useEffect,
  useMemo,
  useState,
  type ComponentType,
  type CSSProperties,
  type ReactNode,
} from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { motion, AnimatePresence } from "motion/react";
import {
  Home,
  Shield,
  Settings2,
  Menu,
  CalendarDays,
  ListTodo,
  BookMarked,
  ChartColumn,
  NotebookPen,
  HeartPulse,
  CircleUserRound,
  MoreHorizontal,
  RefreshCw,
  PanelBottom,
  ClipboardCopy,
  Play,
  RotateCcw,
  Download,
  Terminal,
} from "lucide-react";
import { copyClientErrorLog, getClientErrorLog } from "../lib/clientErrorLog";
import { cn } from "../app/components/ui/utils";
import { useAuth } from "../context/AuthContext";
import { ThemeToggle } from "../components/theme/ThemeToggle";
import { PomodoroDock } from "./topbar/PomodoroDock";
import { focusShellAction } from "../lib/focusBehaviorFile";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "../app/components/ui/dropdown-menu";
import { fetchEnforcerStatusMirror } from "../api/focusMirrors";
import { focusDataUrl } from "../utils/focusDataUrl";
import { resolveFocusShellTitle } from "./pageTitles";
import { ContourStickerLabel } from "../components/theme/ContourStickerLabel";
import { useFocusStatus } from "../hooks/useFocusStatus";
import { dayGateAllowsPath, dayGateTarget, morningLockActive } from "../lib/dayGate";
import { CurvedScrollArea } from "../components/ui/CurvedScrollArea";
import { useTheme } from "../context/ThemeContext";
import { SIDEBAR_STICKER_FONTS } from "../theme/layers";
import {
  focusOwnerDisplayLabel,
  loadFocusOwnerProfile,
} from "../lib/focusOwnerProfile";

/** Icon rail width when peeked / expanded overlay. Pages are full-bleed (no layout inset). */
const RAIL_W = 56;
/** Wider drawer so labels breathe; overlays content (no layout inset). */
const PANEL_W = 300;
/** Idle hit strip so content can use the left edge; hover grows to RAIL_W. */
const EDGE_HIT_W = 10;
const LS_KEY = "sidebar:collapsed";

function postFocusShell(
  action: Parameters<typeof focusShellAction>[0] | "popup_tray" | "ensure_tray" | "quit" | "open_settings" | "reload_ui",
) {
  if (focusShellAction(action as Parameters<typeof focusShellAction>[0])) return true;
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void } };
  };
  if (w.chrome?.webview?.postMessage) {
    w.chrome.webview.postMessage({ type: "focus_shell", v: 1, action });
    return true;
  }
  return false;
}


type NavItem = {
  to?: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  end?: boolean;
};

type NavSection = { id: string; label: string; items: NavItem[] };

function focusSections(): NavSection[] {
  return [
    {
      id: "workspace",
      label: "Workspace",
      items: [
        { to: "/productivity?tab=home", label: "Home", icon: Home },
        { to: "/productivity?tab=calendar", label: "Calendar", icon: CalendarDays },
        { to: "/productivity?tab=plan", label: "Planner", icon: ListTodo },
        { to: "/productivity?tab=analytics", label: "Analytics", icon: ChartColumn },
      ],
    },
    {
      id: "life",
      label: "Life",
      items: [
        { to: "/life", label: "Health", icon: HeartPulse, end: true },
        { to: "/bible", label: "Bible", icon: BookMarked, end: true },
        { to: "/journal", label: "Journal", icon: NotebookPen, end: true },
      ],
    },
    {
      id: "system",
      label: "System",
      items: [{ to: "/productivity?tab=settings", label: "Settings", icon: Settings2 }],
    },
  ];
}

/** SoftLand master (sites) — SoftLand ON ≠ Arm. */
const SETTINGS_SOFTLAND = "/productivity?tab=settings&section=sites";
/** Arm / hard_block_armed (kills) — separate from SoftLand. */
const SETTINGS_ARM = "/productivity?tab=settings&section=unlock";

function StatusDots({ collapsed }: { collapsed: boolean }) {
  const [softlandOn, setSoftlandOn] = useState<boolean | null>(null);
  const [armed, setArmed] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const status = await fetchEnforcerStatusMirror();
        if (!cancelled && status) setArmed(Boolean(status.armed));
        const r = await fetch(focusDataUrl("softland_policy.json"), { cache: "no-store" });
        if (r.ok) {
          const j = (await r.json()) as { softland_enabled?: boolean };
          if (!cancelled && typeof j.softland_enabled === "boolean") {
            setSoftlandOn(j.softland_enabled);
          }
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (softlandOn == null && armed == null) return null;

  const softlandLabel = softlandOn ? "SoftLand on" : "SoftLand off";
  const armLabel = armed ? "Armed" : "Disarmed";
  const softlandTitle =
    "SoftLand = sites · open Settings Site block. SoftLand ON ≠ Armed.";
  const armTitle = "Arm = kills · open Settings Arm. SoftLand ON ≠ Armed.";

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1 py-1" role="group" aria-label="SoftLand and Arm status">
        {softlandOn != null ? (
          <Link
            to={SETTINGS_SOFTLAND}
            className={cn(
              "block h-1.5 w-1.5 rounded-full outline-none transition-opacity hover:opacity-100 focus-visible:ring-2 focus-visible:ring-emerald-400/60",
              softlandOn ? "bg-emerald-400 opacity-90" : "bg-muted-foreground/35 opacity-80",
            )}
            title={softlandTitle}
            aria-label={`${softlandLabel} — open SoftLand settings`}
          />
        ) : null}
        {armed != null ? (
          <Link
            to={SETTINGS_ARM}
            className={cn(
              "block h-1.5 w-1.5 rounded-full outline-none transition-opacity hover:opacity-100 focus-visible:ring-2 focus-visible:ring-rose-400/60",
              armed ? "bg-rose-400 opacity-90" : "bg-muted-foreground/35 opacity-80",
            )}
            title={armTitle}
            aria-label={`${armLabel} — open Arm settings`}
          />
        ) : null}
      </div>
    );
  }

  return (
    <div
      className="focus-sidebar-status"
      role="group"
      aria-label="SoftLand = sites · Arm = kills · SoftLand ON ≠ Armed"
    >
      {softlandOn != null ? (
        <Link
          to={SETTINGS_SOFTLAND}
          className={cn(
            "focus-sidebar-status__chip",
            softlandOn ? "is-on" : "is-off",
          )}
          title={softlandTitle}
          aria-label={`${softlandLabel} — open SoftLand settings`}
        >
          SoftLand {softlandOn ? "on" : "off"}
        </Link>
      ) : null}
      {armed != null ? (
        <Link
          to={SETTINGS_ARM}
          className={cn("focus-sidebar-status__chip", armed ? "is-armed" : "is-off")}
          title={armTitle}
          aria-label={`${armLabel} — open Arm settings`}
        >
          {armLabel}
        </Link>
      ) : null}
    </div>
  );
}

function RailBtn({
  className,
  title,
  "aria-label": ariaLabel,
  onClick,
  children,
}: {
  className?: string;
  title?: string;
  "aria-label": string;
  onClick?: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={ariaLabel}
      onClick={onClick}
      className={cn(
        "focus-rail-btn grid h-9 w-9 shrink-0 place-items-center rounded-xl text-foreground/75 transition-colors",
        "hover:bg-foreground/8 hover:text-foreground",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function FocusSidebar() {
  const [collapsed, setCollapsed] = useState(true);
  /** Peek only while pointer is over the edge/rail — leave hides immediately. */
  const [railHot, setRailHot] = useState(false);
  /** Keep peek open while a tools dropdown is open (portal leaves the rail). */
  const [toolsMenuOpen, setToolsMenuOpen] = useState(false);
  const [ownerLabel, setOwnerLabel] = useState(() => focusOwnerDisplayLabel());
  const { user, isAuthenticated, isAdmin } = useAuth();
  const {
    sidebarStickerFont,
    sidebarStickerScale,
    sidebarStickerCoreFill,
  } = useTheme();
  const location = useLocation();
  const nav = useNavigate();
  const focusStatus = useFocusStatus();
  const gateLocked = morningLockActive(focusStatus);
  const gateTarget = dayGateTarget(focusStatus);
  const openProfileSettings = () => {
    if (gateLocked && gateTarget) {
      nav(gateTarget);
      return;
    }
    nav("/productivity?tab=settings&section=profile");
  };
  const accountTitle = isAuthenticated
    ? user?.display_name || user?.username || ownerLabel
    : ownerLabel;
  const currentTab = new URLSearchParams(location.search).get("tab");
  const sections = useMemo(() => focusSections(), []);
  const pageTitle = resolveFocusShellTitle(location.pathname, currentTab);
  const panelW = collapsed ? RAIL_W : PANEL_W;
  const stickerFontCss = useMemo(() => {
    const f = SIDEBAR_STICKER_FONTS.find((x) => x.id === sidebarStickerFont);
    return f?.css ?? '"Great Vibes", cursive';
  }, [sidebarStickerFont]);
  const stickerFontPx = Math.round(29.6 * (sidebarStickerScale / 100)); // ~1.85rem

  useEffect(() => {
    try {
      const saved = localStorage.getItem(LS_KEY);
      if (saved === "0" || saved === "1") setCollapsed(saved === "1");
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    const sync = () => setOwnerLabel(focusOwnerDisplayLabel(loadFocusOwnerProfile()));
    sync();
    window.addEventListener("calt-focus-owner-profile", sync as EventListener);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("calt-focus-owner-profile", sync as EventListener);
      window.removeEventListener("storage", sync);
    };
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(LS_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  const navItemClass = (active: boolean) =>
    cn(
      "group flex items-center text-[13px] font-medium transition-colors duration-150",
      "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      // Collapsed: fixed 36×36 hit target so the active circle centers on the glyph
      collapsed ? "mx-auto h-9 w-9 justify-center rounded-xl" : "h-9 w-full gap-2.5 rounded-xl px-2",
      active
        ? "bg-primary/15 text-primary hover:bg-primary/20"
        : "text-foreground/70 hover:bg-foreground/6 hover:text-foreground",
    );

  const iconWrapClass = collapsed
    ? "grid h-full w-full place-items-center"
    : "grid h-9 w-9 shrink-0 place-items-center";

  let animIndex = 0;

  return (
    <>
      {!collapsed ? (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-black/20"
          aria-label="Dismiss sidebar"
          onClick={() => setCollapsed(true)}
        />
      ) : null}
      <div
        className={cn(
          "absolute inset-y-0 left-0 z-40",
          /* Expanded: allow sticker contour to paint; collapsed edge still clips peek */
          collapsed ? "focus-sidebar-edge pointer-events-auto overflow-hidden" : "pointer-events-none overflow-visible",
        )}
        style={
          collapsed
            ? ({ ["--focus-edge-hit"]: `${EDGE_HIT_W}px` } as CSSProperties)
            : { width: panelW }
        }
        data-sidebar-overlay="1"
        data-sidebar-collapsed={collapsed ? "1" : "0"}
        data-focus-sidebar="1"
        data-rail-hot={collapsed && railHot ? "1" : "0"}
        onMouseEnter={() => {
          if (collapsed) setRailHot(true);
        }}
        onMouseLeave={() => {
          if (!toolsMenuOpen) setRailHot(false);
        }}
      >
        <nav
          aria-label="Focus"
          className={cn(
            "gloss-sidebar gloss-sidebar--focus group/rail pointer-events-auto flex h-full flex-col transition-[width] duration-300 ease-out",
            collapsed
              ? "gloss-sidebar--autohide overflow-hidden"
              : "gloss-sidebar--focus-open overflow-x-visible overflow-y-hidden",
          )}
          style={{ width: collapsed ? RAIL_W : panelW }}
        >
          {/* Menu only on collapsed/peek rail — expanded drawer uses brand + nav; dismiss via scrim */}
          {collapsed ? (
            <div className="relative flex h-11 shrink-0 items-center px-2">
              <motion.button
                type="button"
                whileTap={{ scale: 0.92 }}
                onClick={() => setCollapsed(false)}
                className="focus-rail-btn absolute top-1/2 z-10 grid h-9 w-9 -translate-y-1/2 place-items-center rounded-xl text-foreground/80 hover:bg-foreground/8 hover:text-foreground"
                style={{ left: (RAIL_W - 36) / 2 }}
                aria-label="Expand sidebar"
                title="Expand sidebar"
              >
                <Menu className="h-[18px] w-[18px]" />
              </motion.button>
            </div>
          ) : null}

          {/* Brand: title sticker only — SoftLand/Arm live at the bottom */}
          <AnimatePresence initial={false}>
            {!collapsed ? (
              <motion.div
                key={`brand-${pageTitle}`}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.18, ease: "easeOut" }}
                className="focus-sidebar-brand"
              >
                <div className="focus-sidebar-sticker-well">
                  <ContourStickerLabel
                    text={pageTitle || "Focus"}
                    fontSizePx={stickerFontPx}
                    fontFamily={stickerFontCss}
                    fill={sidebarStickerCoreFill}
                    className="mx-auto"
                  />
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>

          {/* Primary nav — curved scrollbar when expanded */}
          <CurvedScrollArea
            className="min-h-0 flex-1"
            tone="accent"
            radius={collapsed ? 12 : 22}
            contentClassName={cn(
              "curved-scrollbar__content--flush",
              collapsed
                ? "flex flex-col items-center gap-1 overflow-x-hidden px-0 py-1"
                : "space-y-2.5 overflow-x-hidden px-2.5 py-2",
            )}
          >
            {sections.map((section) => (
              <div
                key={section.id}
                className={cn(collapsed ? "flex w-full flex-col items-center gap-0.5" : "space-y-1")}
              >
                <div
                  className={cn(
                    "overflow-hidden whitespace-nowrap px-2.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/55 transition-opacity duration-200",
                    collapsed ? "h-0 opacity-0 py-0" : "pb-1 pt-0.5 opacity-100",
                  )}
                  aria-hidden={collapsed}
                >
                  {section.label}
                </div>
                <ul
                  className={cn(
                    collapsed ? "flex w-full flex-col items-center gap-0.5" : "space-y-0.5",
                  )}
                >
                  {section.items.map((item) => {
                    const Icon = item.icon;
                    const delay = collapsed ? 0 : Math.min(animIndex++, 16) * 0.018;
                    const to = item.to || "/";
                    const qIdx = to.indexOf("?");
                    const toPath = qIdx >= 0 ? to.slice(0, qIdx) : to;
                    const toSearch = qIdx >= 0 ? to.slice(qIdx) : "";
                    const toTab = toSearch
                      ? new URLSearchParams(toSearch.slice(1)).get("tab")
                      : null;
                    const pathActive = item.end
                      ? location.pathname === toPath
                      : location.pathname === toPath ||
                        location.pathname.startsWith(toPath + "/");
                    const active =
                      toPath === "/productivity" && location.pathname === "/productivity"
                        ? toTab === "home"
                          ? !currentTab || currentTab === "home"
                          : Boolean(toTab) && currentTab === toTab
                        : pathActive && (!toTab || currentTab === toTab);
                    const allowed =
                      !gateLocked || dayGateAllowsPath(focusStatus, `${toPath}${toSearch}`);
                    const dest =
                      allowed || !gateTarget
                        ? toSearch
                          ? { pathname: toPath, search: toSearch }
                          : to
                        : gateTarget;

                    return (
                      <li key={to} className={collapsed ? "flex w-full justify-center" : undefined}>
                        <Link
                          to={dest}
                          aria-current={active ? "page" : undefined}
                          title={
                            collapsed
                              ? item.label
                              : !allowed
                                ? "Finish Bible and today's plan first"
                                : undefined
                          }
                          className={cn(navItemClass(active), !allowed && "opacity-45")}
                        >
                          <span className={iconWrapClass}>
                            <Icon
                              className={cn(
                                "h-[18px] w-[18px] transition-[opacity,color] duration-200",
                                active ? "opacity-100" : "opacity-75 group-hover:opacity-100",
                              )}
                            />
                          </span>
                          {!collapsed ? (
                            <span
                              className="min-w-0 max-w-[10rem] truncate opacity-100 transition-[opacity,max-width] duration-200"
                              style={{ transitionDelay: `${delay * 1000}ms` }}
                            >
                              {item.label}
                            </span>
                          ) : (
                            <span className="sr-only">{item.label}</span>
                          )}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </CurvedScrollArea>

          {/* SoftLand / Arm — bottom of rail, above Tools */}
          <div
            className={cn(
              "focus-sidebar-status-foot shrink-0",
              collapsed ? "px-2 py-1.5" : undefined,
            )}
          >
            <StatusDots collapsed={collapsed} />
          </div>

          {/* Unified tools — same rail size as nav icons */}
          <div
            className={cn(
              "shrink-0 border-t border-border/15",
              collapsed ? "space-y-1 px-2 py-2" : "space-y-2 px-2.5 py-2.5",
            )}
          >
            {!collapsed ? (
              <div className="px-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/55">
                Tools
              </div>
            ) : null}
            <div
              className={cn(
                "flex",
                collapsed ? "flex-col items-center gap-1" : "flex-wrap items-center gap-1",
              )}
            >
              <div className="grid h-9 w-9 place-items-center overflow-hidden">
                <PomodoroDock align="start" side="top" compact />
              </div>
              <div className="grid h-9 w-9 place-items-center overflow-hidden [&_button]:!h-9 [&_button]:!w-9 [&_button]:!min-h-0 [&_button]:!rounded-xl [&_button]:!p-0">
                <ThemeToggle size="sm" />
              </div>

              <DropdownMenu
                onOpenChange={(open) => {
                  setToolsMenuOpen(open);
                  if (open && collapsed) setRailHot(true);
                }}
              >
                <DropdownMenuTrigger asChild>
                  <RailBtn aria-label="Account" title={accountTitle}>
                    <CircleUserRound className="h-[18px] w-[18px]" />
                  </RailBtn>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" side="top" className="w-52" sideOffset={8}>
                  <DropdownMenuLabel>{accountTitle}</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={openProfileSettings}>
                    <CircleUserRound className="mr-2 h-4 w-4" />
                    Profile settings
                  </DropdownMenuItem>
                  {isAdmin ? (
                    <DropdownMenuItem onClick={() => nav("/admin")}>
                      <Shield className="mr-2 h-4 w-4" />
                      Admin Panel
                    </DropdownMenuItem>
                  ) : null}
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Tray mirror — keep; useful when system tray is hard to reach */}
              <DropdownMenu
                onOpenChange={(open) => {
                  setToolsMenuOpen(open);
                  if (open && collapsed) setRailHot(true);
                }}
              >
                <DropdownMenuTrigger asChild>
                  <RailBtn aria-label="Focus menu" title="Tray actions in-app">
                    <MoreHorizontal className="h-[18px] w-[18px]" />
                  </RailBtn>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" side="top" className="w-64" sideOffset={8}>
                  <DropdownMenuLabel>CALT Focus</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={() => {
                      if (gateLocked && gateTarget) nav(gateTarget);
                      else nav("/productivity?tab=home");
                    }}
                  >
                    <Home className="mr-2 h-4 w-4" />
                    Open Focus
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => {
                      if (gateLocked && gateTarget) nav(gateTarget);
                      else nav("/productivity?tab=calendar");
                    }}
                  >
                    <CalendarDays className="mr-2 h-4 w-4" />
                    Open Calendar
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => {
                      if (gateLocked && gateTarget && !gateTarget.includes("tab=plan")) {
                        nav(gateTarget);
                      } else {
                        nav("/productivity?tab=plan");
                      }
                    }}
                  >
                    <ListTodo className="mr-2 h-4 w-4" />
                    Open Plan
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => {
                      if (gateLocked && gateTarget) {
                        nav(gateTarget);
                        return;
                      }
                      if (!postFocusShell("open_settings")) {
                        nav("/productivity?tab=settings");
                      }
                    }}
                  >
                    <Settings2 className="mr-2 h-4 w-4" />
                    Open Settings
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => postFocusShell("ensure_enforcer")}>
                    <Play className="mr-2 h-4 w-4" />
                    Ensure enforcer + open
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => postFocusShell("restart_enforcer")}>
                    <RotateCcw className="mr-2 h-4 w-4" />
                    Restart CALT (enforcer + UI)
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={() => {
                      if (!postFocusShell("reload_ui")) window.location.reload();
                    }}
                  >
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Reload UI
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => postFocusShell("update_ui")}>
                    <Download className="mr-2 h-4 w-4" />
                    Update UI (rebuild + reload)
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger>
                      <Terminal className="mr-2 h-4 w-4" />
                      Rebuild
                    </DropdownMenuSubTrigger>
                    <DropdownMenuSubContent className="w-60">
                      <DropdownMenuItem onClick={() => postFocusShell("update_stack")}>
                        Update stack (UI + natives + rules)
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => postFocusShell("apply_update")}>
                        Apply pending update & restart
                      </DropdownMenuItem>
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => postFocusShell("popup_tray")}>
                    <PanelBottom className="mr-2 h-4 w-4" />
                    Show tray menu
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => postFocusShell("ensure_tray")}>
                    <PanelBottom className="mr-2 h-4 w-4" />
                    Find tray icon
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => {
                      void copyClientErrorLog().then((r) => {
                        const n = r.count || getClientErrorLog().length;
                        if (r.ok) console.info(`[CALT] Copied ${n} client error(s)`);
                        else console.warn("[CALT] Copy error log failed", r.error);
                      });
                    }}
                  >
                    <ClipboardCopy className="mr-2 h-4 w-4" />
                    Copy error log
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-rose-300 focus:text-rose-200"
                    onClick={() => postFocusShell("quit")}
                  >
                    Quit
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </nav>
      </div>
    </>
  );
}
