import {
  useEffect,
  useMemo,
  useState,
  type ComponentType,
} from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router";
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
  BookOpen,
  CircleUserRound,
  MoreHorizontal,
  RefreshCw,
  PanelBottom,
  ClipboardCopy,
} from "lucide-react";
import { copyClientErrorLog, getClientErrorLog } from "../lib/clientErrorLog";
import { cn } from "../app/components/ui/utils";
import { useAuth } from "../context/AuthContext";
import { usePluginsOptional } from "../plugins/registry";
import type { PluginNavItem } from "../plugins/types";
import {
  NAV_SECTION_LABELS,
  NAV_SECTION_ORDER,
  navPathRank,
  resolveNavSection,
  type NavSectionId,
} from "./navSections";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";
import { ThemeToggle } from "../components/theme/ThemeToggle";
import { PomodoroDock } from "./topbar/PomodoroDock";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../app/components/ui/dropdown-menu";
import { fetchEnforcerStatusMirror } from "../api/focusMirrors";
import { focusDataUrl } from "../utils/focusDataUrl";
import { resolveFocusShellTitle } from "./pageTitles";
import { FocusSidebar } from "./FocusSidebar";

const LS_KEY = "sidebar:collapsed";
export const SIDEBAR_RAIL_PX = 56;
const RAIL_W = SIDEBAR_RAIL_PX;
const PANEL_W = 224;

/** Study FE (Vite) preferred; API-only hosts can still open docs later. */
const STUDY_SITE_URL = "http://127.0.0.1:5173/";

function openStudyInBrowser() {
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void } };
  };
  if (w.chrome?.webview?.postMessage) {
    w.chrome.webview.postMessage({ type: "open_external", v: 1, url: STUDY_SITE_URL });
    return;
  }
  window.open(STUDY_SITE_URL, "_blank", "noopener,noreferrer");
}

function postFocusShell(action: string) {
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void } };
  };
  if (w.chrome?.webview?.postMessage) {
    w.chrome.webview.postMessage({ type: "focus_shell", v: 1, action });
    return true;
  }
  return false;
}

type SidebarItem = PluginNavItem & { end?: boolean };

function groupBySection(items: SidebarItem[]): { id: NavSectionId; label: string; items: SidebarItem[] }[] {
  const buckets: Record<NavSectionId, SidebarItem[]> = {
    study: [],
    focus: [],
    life: [],
    system: [],
  };
  for (const item of items) {
    const section = resolveNavSection(item.to, item.category ?? null);
    buckets[section].push(item);
  }
  for (const id of NAV_SECTION_ORDER) {
    buckets[id].sort((a, b) => navPathRank(a.to) - navPathRank(b.to));
  }
  return NAV_SECTION_ORDER.filter((id) => buckets[id].length > 0).map((id) => ({
    id,
    label: NAV_SECTION_LABELS[id],
    items: buckets[id],
  }));
}

/** Blocker + day loop only — study stays in the browser webapp. */
function focusShellSections(): { id: NavSectionId; label: string; items: SidebarItem[] }[] {
  return [
    {
      id: "focus",
      label: "Workspace",
      items: [
        { to: "/productivity?tab=home", label: "Home", icon: Home, end: false, category: "focus" },
        { to: "/productivity?tab=calendar", label: "Calendar", icon: CalendarDays, end: false, category: "focus" },
        { to: "/productivity?tab=plan", label: "Planner", icon: ListTodo, end: false, category: "focus" },
        { to: "/productivity?tab=analytics", label: "Analytics", icon: ChartColumn, end: false, category: "focus" },
      ],
    },
    {
      id: "life",
      label: "Life",
      items: [
        { to: "/bible", label: "Bible", icon: BookMarked, end: true, category: "focus" },
        { to: "/journal", label: "Journal", icon: NotebookPen, end: true, category: "focus" },
      ],
    },
    {
      id: "system",
      label: "System",
      items: [
        {
          to: "/productivity?tab=settings",
          label: "Settings",
          icon: Settings2,
          end: false,
          category: "focus",
        },
      ],
    },
  ];
}

function FocusStatusChips({ collapsed }: { collapsed: boolean }) {
  const [softlandOn, setSoftlandOn] = useState<boolean | null>(null);
  const [armed, setArmed] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const status = await fetchEnforcerStatusMirror();
        if (cancelled) return;
        if (status) setArmed(Boolean(status.armed));
        try {
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
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (softlandOn == null && armed == null) return null;

  const statusLabel = [
    softlandOn != null ? (softlandOn ? "SoftLand on" : "SoftLand off") : null,
    armed != null ? (armed ? "Armed" : "Disarmed") : null,
  ]
    .filter(Boolean)
    .join(" · ");

  if (collapsed) {
    return (
      <div
        className="flex flex-col items-center gap-1 px-1"
        aria-label={statusLabel || "SoftLand status"}
        title={statusLabel || "SoftLand status"}
      >
        {softlandOn != null ? (
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              softlandOn ? "bg-emerald-400" : "bg-muted-foreground/40",
            )}
            aria-label={softlandOn ? "SoftLand on" : "SoftLand off"}
          />
        ) : null}
        {armed != null ? (
          <span
            className={cn("h-2 w-2 rounded-full", armed ? "bg-rose-400" : "bg-muted-foreground/40")}
            aria-label={armed ? "Armed" : "Disarmed"}
          />
        ) : null}
      </div>
    );
  }

  return (
    <div
      className="flex flex-wrap gap-1.5 px-0.5"
      title="SoftLand = sites · Arm = kills · SoftLand ON ≠ Armed"
    >
      {softlandOn != null ? (
        <span
          className={cn(
            "text-[10px] font-mono px-2 py-1 rounded-md border tracking-wide",
            softlandOn
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-border/50 text-muted-foreground",
          )}
        >
          SoftLand {softlandOn ? "on" : "off"}
        </span>
      ) : null}
      {armed != null ? (
        <span
          className={cn(
            "text-[10px] font-mono px-2 py-1 rounded-md border tracking-wide",
            armed
              ? "border-rose-500/30 bg-rose-500/10 text-rose-300"
              : "border-border/50 text-muted-foreground",
          )}
        >
          {armed ? "Armed" : "Disarmed"}
        </span>
      ) : null}
    </div>
  );
}

function FocusSidebarFooter({ collapsed }: { collapsed: boolean }) {
  const nav = useNavigate();
  const { user, isAuthenticated, isAdmin } = useAuth();

  return (
    <div
      className={cn(
        "sidebar-focus-footer shrink-0",
        collapsed
          ? "space-y-1.5 overflow-hidden border-t border-border/20 px-1 py-2"
          : "space-y-2 overflow-hidden border-t border-border/20 px-2.5 pb-3 pt-2",
      )}
    >
      <FocusStatusChips collapsed={collapsed} />

      <div
        className={cn(
          "flex items-center",
          collapsed ? "flex-col gap-1.5" : "flex-nowrap gap-2",
        )}
      >
        <div className={cn(collapsed && "mx-auto")}>
          <PomodoroDock align="start" side="top" compact={collapsed} />
        </div>
        <div className={cn(collapsed && "mx-auto")}>
          <ThemeToggle size="sm" />
        </div>
      </div>

      <div
        className={cn(
          "flex",
          collapsed ? "flex-col items-stretch gap-1" : "items-center gap-1.5",
        )}
      >
        <button
          type="button"
          onClick={openStudyInBrowser}
          className={cn(
            "gloss-dock-btn inline-flex items-center gap-1.5 rounded-xl text-xs font-medium text-foreground/90 hover:scale-[1.02] transition-transform",
            collapsed ? "h-9 w-9 justify-center p-0 mx-auto" : "flex-1 min-w-0 px-2.5 py-2",
          )}
          title="Open CALT Study in your browser"
          aria-label="Open Study"
        >
          <BookOpen className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span
            className={cn(
              "truncate overflow-hidden transition-[opacity,max-width] duration-200",
              collapsed ? "max-w-0 opacity-0" : "max-w-[8rem] opacity-100",
            )}
          >
            Open Study
          </span>
        </button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className={cn("gloss-dock-btn rounded-xl p-2 hover:scale-105 transition-transform", collapsed && "mx-auto")}
              aria-label="Account menu"
              title={isAuthenticated ? user?.display_name || user?.username : "Profile"}
            >
              <CircleUserRound className="w-4 h-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" side="top" className="w-52">
            <DropdownMenuLabel>
              {isAuthenticated ? user?.display_name || user?.username || "Owner" : "This machine"}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => nav("/profile")}>
              <CircleUserRound className="w-4 h-4 mr-2" />
              Profile
            </DropdownMenuItem>
            {isAdmin && (
              <DropdownMenuItem onClick={() => nav("/admin")}>
                <Shield className="w-4 h-4 mr-2" />
                Admin Panel
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className={cn("gloss-dock-btn rounded-xl p-2 hover:scale-105 transition-transform", collapsed && "mx-auto")}
              aria-label="Focus menu"
              title="Focus menu — tray fallback"
            >
              <MoreHorizontal className="h-4 w-4" aria-hidden />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" side="top" className="w-56">
            <DropdownMenuLabel>CALT Focus</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                if (!postFocusShell("reload_ui")) window.location.reload();
              }}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Reload UI
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                if (!postFocusShell("open_settings")) {
                  nav("/productivity?tab=settings");
                }
              }}
            >
              <Settings2 className="w-4 h-4 mr-2" />
              Open Settings
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => postFocusShell("popup_tray")}>
              <PanelBottom className="w-4 h-4 mr-2" />
              Show tray menu
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => postFocusShell("ensure_tray")}>
              <PanelBottom className="w-4 h-4 mr-2" />
              Find tray icon
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                void copyClientErrorLog().then((r) => {
                  const n = r.count || getClientErrorLog().length;
                  if (r.ok) {
                    console.info(`[CALT] Copied ${n} client error(s) to clipboard`);
                  } else {
                    console.warn("[CALT] Copy error log failed", r.error);
                  }
                });
              }}
            >
              <ClipboardCopy className="w-4 h-4 mr-2" />
              Copy error log
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-rose-300 focus:text-rose-200"
              onClick={() => postFocusShell("quit")}
            >
              Quit Focus
            </DropdownMenuItem>
            <p className="px-2 py-1.5 text-[10px] text-muted-foreground leading-snug">
              Win11 often hides tray icons — click ^ near the clock and pin CALT Focus.
            </p>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

export function AppSidebar() {
  const shell = isFocusDesktopShell();
  if (shell) return <FocusSidebar />;

  const [collapsed, setCollapsed] = useState(true);
  const { isAdmin } = useAuth();
  const plugins = usePluginsOptional();
  const location = useLocation();
  const currentTab = new URLSearchParams(location.search).get("tab");

  const sections = useMemo(() => {
    if (shell) return focusShellSections();
    const base: SidebarItem[] = [
      { to: "/", label: "Home", icon: Home, end: true, category: "system" },
      ...(plugins?.getNavItems() ?? []),
      { to: "/settings", label: "Settings", icon: Settings2, end: false, category: "system" },
      { to: "/admin", label: "Admin", icon: Shield, end: false, category: "system" },
    ];
    const filtered = base.filter((item) => item.label !== "Admin" || isAdmin);
    const seen = new Set<string>();
    const unique = filtered.filter((item) => {
      if (seen.has(item.to)) return false;
      seen.add(item.to);
      return true;
    });
    return groupBySection(unique);
  }, [plugins, isAdmin, shell]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(LS_KEY);
      if (saved === "0" || saved === "1") setCollapsed(saved === "1");
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(LS_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  let animIndex = 0;

  const pageTitle = shell
    ? resolveFocusShellTitle(location.pathname, currentTab)
    : null;

  const panelW = collapsed ? RAIL_W : PANEL_W;

  const navItemClass = (active: boolean) =>
    cn(
      "group flex h-9 w-full items-center gap-2.5 rounded-xl px-2 text-[13px] font-medium transition-colors duration-150",
      "focus:outline-none focus:ring-2 focus:ring-ring",
      collapsed && "justify-center px-0",
      active
        ? shell
          ? "bg-primary/15 text-primary hover:bg-primary/20"
          : "bg-primary/12 text-primary hover:bg-primary/18"
        : "text-foreground/70 hover:bg-foreground/6 hover:text-foreground",
    );

  return (
    <>
      {!collapsed ? (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-black/15"
          aria-label="Dismiss sidebar"
          onClick={() => setCollapsed(true)}
        />
      ) : null}
      <div
        className="pointer-events-none absolute inset-y-0 left-0 z-40"
        style={{ width: panelW }}
        data-sidebar-overlay="1"
        data-sidebar-collapsed={collapsed ? "1" : "0"}
      >
        <nav
          aria-label="Main"
          className={cn(
            "gloss-sidebar group/rail pointer-events-auto flex h-full w-full flex-col transition-[width] duration-300 ease-out",
            collapsed
              ? "gloss-sidebar--autohide overflow-hidden"
              : "gloss-sidebar--overlay gloss-sidebar--overlay-open overflow-hidden",
          )}
          style={{ width: panelW }}
        >
          <div
            className={cn(
              "sidebar-rail-header relative flex h-14 shrink-0 items-center",
              collapsed ? "px-2" : "border-b border-border/20 px-2.5",
            )}
          >
            <motion.button
              type="button"
              whileTap={{ scale: 0.92 }}
              onClick={() => setCollapsed((v) => !v)}
              className="sidebar-bible-card__btn absolute top-1/2 z-10 -translate-y-1/2"
              style={{ left: (RAIL_W - 32) / 2 }}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              <Menu className="h-4 w-4" />
            </motion.button>
            <AnimatePresence initial={false}>
              {!collapsed && (
                <motion.div
                  key={shell ? `title-${pageTitle}` : "brand"}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -4 }}
                  transition={{ duration: 0.2, ease: "easeOut" }}
                  className="min-w-0 pl-14 pr-1.5"
                >
                  {shell && pageTitle ? (
                    <div className="topbar-title-card sidebar-page-title min-w-0">
                      <h1
                        className="topbar-title-card__heading"
                        data-outline="triple"
                        data-text={pageTitle}
                      >
                        {pageTitle}
                      </h1>
                    </div>
                  ) : (
                    <span className="sidebar-bible-card__brand">
                      <span className="sidebar-bible-card__mark" aria-hidden />
                      Study Hub
                    </span>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div
            className={cn(
              "flex-1 bg-transparent",
              collapsed
                ? "sidebar-ghost-scroll space-y-2 overflow-y-auto overflow-x-hidden px-2 py-2"
                : "space-y-2.5 overflow-y-auto overflow-x-hidden px-2.5 py-2.5",
            )}
          >
            {sections.map((section) => (
              <div key={section.id} className={collapsed ? "space-y-0.5" : "space-y-1"}>
                <div
                  className={cn(
                    "overflow-hidden whitespace-nowrap text-[10px] font-semibold uppercase transition-opacity duration-200",
                    shell
                      ? "px-2.5 pb-1 pt-0.5 tracking-[0.14em] text-muted-foreground/55"
                      : "px-2.5 pb-0.5 pt-1 tracking-wider text-muted-foreground/70",
                    collapsed ? "h-0 opacity-0 py-0 pt-0 pb-0" : "opacity-100",
                  )}
                  role="presentation"
                  aria-hidden={collapsed}
                >
                  {section.label}
                </div>
                <ul className="space-y-0.5">
                  {section.items.map(({ to, label, icon: Icon, end }) => {
                    const delay = collapsed ? 0 : Math.min(animIndex++, 16) * 0.018;
                    const IconComp = Icon as ComponentType<{ className?: string }>;
                    const qIdx = to.indexOf("?");
                    const toPath = qIdx >= 0 ? to.slice(0, qIdx) : to;
                    const toSearch = qIdx >= 0 ? to.slice(qIdx) : "";
                    const toTab = toSearch ? new URLSearchParams(toSearch.slice(1)).get("tab") : null;
                    const pathActive =
                      end
                        ? location.pathname === toPath
                        : location.pathname === toPath || location.pathname.startsWith(toPath + "/");
                    const active =
                      shell && toPath === "/productivity" && location.pathname === "/productivity"
                        ? toTab === "home"
                          ? !currentTab || currentTab === "home"
                          : Boolean(toTab) && currentTab === toTab
                        : pathActive && (!toTab || currentTab === toTab);
                    const LinkComp = shell && toPath === "/productivity" ? Link : NavLink;
                    const linkBody = (
                      <>
                        <span className="grid h-9 w-9 shrink-0 place-items-center">
                          <IconComp
                            className={cn(
                              "h-[18px] w-[18px] transition-[opacity,transform,color] duration-200",
                              active
                                ? "scale-105 opacity-100"
                                : "opacity-[0.75] group-hover:opacity-100",
                            )}
                          />
                        </span>
                        <span
                          className={cn(
                            "min-w-0 truncate overflow-hidden transition-[opacity,max-width] duration-200",
                            collapsed ? "max-w-0 opacity-0" : "max-w-[10rem] opacity-100",
                          )}
                          style={{ transitionDelay: collapsed ? "0ms" : `${delay * 1000}ms` }}
                        >
                          {label}
                        </span>
                      </>
                    );
                    return (
                      <li key={to}>
                        <LinkComp
                          to={toSearch ? { pathname: toPath, search: toSearch } : to}
                          {...(LinkComp === NavLink ? { end } : {})}
                          aria-current={active ? "page" : undefined}
                          title={collapsed ? label : undefined}
                          className={
                            LinkComp === NavLink
                              ? () => navItemClass(active)
                              : navItemClass(active)
                          }
                        >
                          {LinkComp === NavLink ? () => linkBody : linkBody}
                        </LinkComp>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>

          {shell ? <FocusSidebarFooter collapsed={collapsed} /> : null}
        </nav>
      </div>
    </>
  );
}
