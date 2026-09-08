import { useEffect, useMemo, useState, type ComponentType } from "react";
import { NavLink } from "react-router";
import { motion, AnimatePresence } from "motion/react";
import { Home, Shield, Settings2, Menu, CalendarDays, ListTodo, Crosshair } from "lucide-react";
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

const LS_KEY = "sidebar:collapsed";

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

/** Blocker + calendar/plan only — study stays in the browser webapp. */
function focusShellSections(): { id: NavSectionId; label: string; items: SidebarItem[] }[] {
  return [
    {
      id: "focus",
      label: "Desktop",
      items: [
        { to: "/productivity", label: "Calendar", icon: CalendarDays, end: true, category: "focus" },
        { to: "/productivity?tab=plan", label: "Plan", icon: ListTodo, end: false, category: "focus" },
        {
          to: "/productivity?tab=settings",
          label: "Settings",
          icon: Settings2,
          end: false,
          category: "focus",
        },
        { to: "/productivity/focus", label: "Focus", icon: Crosshair, end: true, category: "focus" },
      ],
    },
  ];
}

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(true);
  const { isAdmin } = useAuth();
  const plugins = usePluginsOptional();
  const shell = isFocusDesktopShell();

  const sections = useMemo(() => {
    if (shell) return focusShellSections();
    const base: SidebarItem[] = [
      { to: "/", label: "Home", icon: Home, end: true, category: "system" },
      ...(plugins?.getNavItems() ?? []),
      { to: "/settings", label: "Settings", icon: Settings2, end: false, category: "system" },
      { to: "/admin", label: "Admin", icon: Shield, end: false, category: "system" },
    ];
    const filtered = base.filter((item) => item.label !== "Admin" || isAdmin);
    // Dedupe by path (first wins) in case plugins overlap
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

  return (
    <nav
      aria-label="Main"
      className={cn(
        "gloss-sidebar group/rail flex flex-col h-full shrink-0 transition-[width] duration-300 ease-out",
        collapsed ? "w-14" : "w-52",
      )}
    >
      <div
        className={cn(
          "flex shrink-0 items-center",
          collapsed ? "h-16 justify-center px-1" : "h-16 justify-center px-2",
        )}
      >
        <div className={cn("sidebar-bible-card", collapsed ? "" : "w-full justify-between")}>
          <AnimatePresence initial={false} mode="popLayout">
            {!collapsed && (
              <motion.span
                key="brand"
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -6 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
                className="sidebar-bible-card__brand min-w-0"
              >
                <span className="sidebar-bible-card__mark" aria-hidden />
                {shell ? "CALT Focus" : "Study Hub"}
              </motion.span>
            )}
          </AnimatePresence>
          <motion.button
            type="button"
            whileTap={{ scale: 0.92 }}
            onClick={() => setCollapsed((v) => !v)}
            className="sidebar-bible-card__btn"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <Menu className="h-4 w-4" />
          </motion.button>
        </div>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto overflow-x-hidden px-2 py-2.5 bg-transparent">
        {sections.map((section) => (
          <div key={section.id} className="space-y-1">
            {!collapsed && (
              <div
                className="px-2.5 pt-1 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70"
                role="presentation"
              >
                {section.label}
              </div>
            )}
            <ul className="space-y-1">
              {section.items.map(({ to, label, icon: Icon, end }) => {
                const delay = collapsed ? 0 : Math.min(animIndex++, 16) * 0.018;
                const IconComp = Icon as ComponentType<{ className?: string }>;
                return (
                  <motion.li
                    key={to}
                    initial={false}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.18, delay }}
                  >
                    <NavLink
                      to={to}
                      end={end}
                      title={collapsed ? `${section.label} · ${label}` : undefined}
                      className={({ isActive }) =>
                        cn(
                          "group flex items-center rounded-lg text-[13px] font-medium transition-colors duration-150",
                          collapsed ? "h-9 w-9 justify-center p-0 mx-auto" : "gap-2.5 px-2.5 py-2",
                          "focus:outline-none focus:ring-2 focus:ring-ring",
                          isActive
                            ? "bg-primary/12 text-primary hover:bg-primary/18"
                            : "text-foreground/70 hover:bg-foreground/6 hover:text-foreground",
                        )
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <IconComp
                            className={cn(
                              "h-[18px] w-[18px] shrink-0 transition-[opacity,transform,color] duration-200",
                              isActive
                                ? "scale-105 opacity-100"
                                : "opacity-[0.55] group-hover:opacity-100 group-hover/rail:opacity-100",
                            )}
                          />
                          <AnimatePresence initial={false}>
                            {!collapsed && (
                              <motion.span
                                key="label"
                                initial={{ opacity: 0, width: 0 }}
                                animate={{ opacity: 1, width: "auto" }}
                                exit={{ opacity: 0, width: 0 }}
                                transition={{ duration: 0.15 }}
                                className="truncate overflow-hidden"
                              >
                                {label}
                              </motion.span>
                            )}
                          </AnimatePresence>
                        </>
                      )}
                    </NavLink>
                  </motion.li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </nav>
  );
}
