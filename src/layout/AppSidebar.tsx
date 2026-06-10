import { useEffect, useState } from "react";
import { NavLink } from "react-router";
import {
  Home,
  Brain,
  BookOpen,
  Shield,
  Settings2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "../app/components/ui/utils";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";

import { usePlugins } from "../plugins/registry";

const LS_KEY = "sidebar:collapsed";

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(true);
  const { isAdmin } = useAuth();
  const { getNavItems } = usePlugins();
  const { typographyPack } = useTheme();
  const titleClass =
    typographyPack !== "study" ? "hero-label text-primary" : "text-sm font-semibold";
  
  const baseNavItems = [
    { to: "/", label: "Home", icon: Home, end: true },
    ...getNavItems(),
    { to: "/settings", label: "Settings", icon: Settings2, end: false },
    { to: "/admin", label: "Admin", icon: Shield, end: false },
  ];
  const activeNavItems = baseNavItems.filter(item => item.label !== "Admin" || isAdmin);

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
        "gloss-sidebar flex flex-col h-full shrink-0 transition-all duration-300 ease-in-out",
        collapsed ? "w-14" : "w-56"
      )}
    >
      <div className="flex items-center justify-between p-2 border-b border-border/50">
        {!collapsed && (
          <span className={cn("px-2 truncate", titleClass)}>Study Hub</span>
        )}
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className="ml-auto p-2 rounded-lg hover:bg-accent/80 focus:outline-none focus:ring-2 focus:ring-ring"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronLeft className="w-4 h-4" />
          )}
        </button>
      </div>

      <ul className="flex-1 space-y-1 p-2 overflow-y-auto">
        {activeNavItems.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                  "hover:bg-accent/70 focus:outline-none focus:ring-2 focus:ring-ring",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-foreground/80"
                )
              }
            >
              <Icon className="w-5 h-5 shrink-0" />
              {!collapsed && <span className="truncate">{label}</span>}
            </NavLink>
          </li>
        ))}
      </ul>

      <div className="p-2 text-[10px] text-muted-foreground select-none border-t border-border/50">
        {!collapsed ? "Cognitive Study Companion" : "CSC"}
      </div>
    </nav>
  );
}
