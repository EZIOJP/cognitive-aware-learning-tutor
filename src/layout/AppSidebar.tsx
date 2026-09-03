import { useEffect, useMemo, useState } from "react";
import { NavLink } from "react-router";
import { motion, AnimatePresence } from "motion/react";
import { Home, Shield, Settings2, Menu } from "lucide-react";
import { cn } from "../app/components/ui/utils";
import { useAuth } from "../context/AuthContext";
import { usePluginsOptional } from "../plugins/registry";

const LS_KEY = "sidebar:collapsed";

/** Preferred sidebar order — study loop first, tools, then AI, then system. */
const NAV_ORDER: string[] = [
  "/",
  "/lecture-notes",
  "/review",
  "/journal",
  "/bible",
  "/gre-vocab",
  "/math-tutor",
  "/productivity",
  "/life-tracker",
  "/nutrition",
  "/settings",
  "/admin",
];

function navRank(to: string): number {
  const i = NAV_ORDER.indexOf(to);
  return i >= 0 ? i : 500 + to.length;
}

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(true);
  const { isAdmin } = useAuth();
  const plugins = usePluginsOptional();

  const activeNavItems = useMemo(() => {
    const base = [
      { to: "/", label: "Home", icon: Home, end: true },
      ...(plugins?.getNavItems() ?? []),
      { to: "/settings", label: "Settings", icon: Settings2, end: false },
      { to: "/admin", label: "Admin", icon: Shield, end: false },
    ];
    return base
      .filter((item) => item.label !== "Admin" || isAdmin)
      .sort((a, b) => navRank(a.to) - navRank(b.to));
  }, [plugins, isAdmin]);

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
        <div
          className={cn(
            "sidebar-bible-card",
            collapsed ? "" : "w-full justify-between",
          )}
        >
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
                Study Hub
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

      <ul className="flex-1 space-y-2 overflow-y-auto overflow-x-hidden px-2 py-2.5 bg-transparent">
        {activeNavItems.map(({ to, label, icon: Icon, end }, index) => (
          <motion.li
            key={to}
            initial={false}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18, delay: collapsed ? 0 : Math.min(index, 12) * 0.018 }}
          >
            <NavLink
              to={to}
              end={end}
              title={collapsed ? label : undefined}
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
                  <Icon
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
        ))}
      </ul>
    </nav>
  );
}
