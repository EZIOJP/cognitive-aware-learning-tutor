import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { useLocation, useNavigate } from "react-router";
import { CircleUserRound, LogOut, Shield, LogIn } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { ThemeToggle } from "../components/theme/ThemeToggle";
import { useAuth } from "../context/AuthContext";
import { PomodoroDock } from "./topbar/PomodoroDock";
import { FaceTrackerDock } from "./topbar/FaceTrackerDock";
import { DashboardChromeDock } from "./topbar/DashboardChromeDock";
import { usePluginsOptional } from "../plugins/registry";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../app/components/ui/dropdown-menu";

const LONG_PRESS_MS = 600;
const ROCKET_COLOR = "#fb923c";

/** Flat rocket pointing exactly right (0°) — Lucide’s is diagonal. */
function FlatRocket({ color, className }: { color: string; className?: string }) {
  return (
    <svg
      viewBox="0 0 28 14"
      width="28"
      height="14"
      className={className}
      aria-hidden
    >
      <path
        d="M2 7 L8 3.5 L20 3.5 L26 7 L20 10.5 L8 10.5 Z"
        fill={color}
        stroke="rgba(255,255,255,0.35)"
        strokeWidth="0.6"
      />
      <path d="M20 3.5 L26 7 L20 10.5 Z" fill="#fff" fillOpacity="0.85" />
      <circle cx="14" cy="7" r="1.6" fill="#0f172a" opacity="0.55" />
      <path d="M8 3.5 L5 1 L9 3.5 Z" fill={color} />
      <path d="M8 10.5 L5 13 L9 10.5 Z" fill={color} />
    </svg>
  );
}

/** Exact + nested route titles. Longest prefix wins for child paths. */
const PAGE_TITLES: Record<string, string> = {
  "/": "Study Hub",
  "/login": "Sign in",
  "/admin": "Admin",
  "/profile": "Profile",
  "/settings": "Settings",
  "/settings/ai": "AI Control",
  "/settings/theme": "Theme",
  "/settings/plugins": "Plugins",
  "/settings/features": "Feature Studio",
  "/math-tutor": "Math Tutor",
  "/math-tutor/reports": "Math Reports",
  "/math-tutor/recognize-test": "Math Recognize",
  "/math-tutor/train": "Math Train",
  "/gre-vocab": "GRE Vocabulary",
  "/gre-vocab/add-words": "Add Words",
  "/gre-vocab/read": "Vocab Read",
  "/gre-vocab/cycle": "Vocab Cycle",
  "/lecture-notes": "Lecture Notes",
  "/review": "Review Hub",
  "/study-room": "Study Room",
  "/hub": "Cortex Hub",
  "/ai-coach": "AI Coach",
  "/project-agent": "Project Agent",
  "/journal": "Journal",
  "/productivity": "Productivity",
  "/life-tracker": "Life Tracker",
  "/nutrition": "Nutrition",
  "/system-logs": "App Logs",
  "/focus/calibrate": "Focus Calibrate",
};

const PAGE_SUBTITLES: Record<string, string> = {
  "/": "Your daily learning home",
  "/gre-vocab": "Adaptive vocabulary practice",
  "/math-tutor": "Topics, drills, and progress",
  "/productivity": "Plan, track, and review focus",
  "/lecture-notes": "Capture and study lectures",
  "/review": "Spaced repetition due today",
  "/settings": "Appearance, AI, and plugins",
  "/settings/theme": "Preview and switch look",
  "/hub": "Multi-agent study cortex",
  "/ai-coach": "Personal study coaching",
  "/journal": "Reflect and track mood",
  "/life-tracker": "Habits and life score",
  "/nutrition": "Macros and meals",
};

function matchLongestPrefix(pathname: string, table: Record<string, string>): string | null {
  let best: string | null = null;
  let bestLen = -1;
  for (const [path, label] of Object.entries(table)) {
    if (path === "/") {
      if (pathname === "/" && path.length > bestLen) {
        best = label;
        bestLen = path.length;
      }
      continue;
    }
    if ((pathname === path || pathname.startsWith(`${path}/`)) && path.length > bestLen) {
      best = label;
      bestLen = path.length;
    }
  }
  return best;
}

function humanizeSegment(segment: string): string {
  return segment
    .split("-")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function resolvePageTitle(
  pathname: string,
  navItems: { to: string; label: string }[]
): string {
  const fromMap = matchLongestPrefix(pathname, PAGE_TITLES);
  if (fromMap) return fromMap;

  let bestLabel: string | null = null;
  let bestLen = -1;
  for (const item of navItems) {
    const path = item.to.startsWith("/") ? item.to : `/${item.to}`;
    if (path === "/") continue;
    if ((pathname === path || pathname.startsWith(`${path}/`)) && path.length > bestLen) {
      bestLabel = item.label;
      bestLen = path.length;
    }
  }
  if (bestLabel) return bestLabel;

  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) return "Study Hub";
  return humanizeSegment(segments[segments.length - 1] ?? "Study Companion");
}

/** Plan: top bar = profile, theme, pomodoro only. EEG / mirror live on dashboard & plugin pages. */
export function AppTopBar() {
  const nav = useNavigate();
  const { pathname } = useLocation();
  const { user, isAuthenticated, isAdmin, logout } = useAuth();
  const plugins = usePluginsOptional();
  const focusMirrorOn =
    Boolean(plugins?.isLoaded) && (plugins?.enabledIds.includes("focus-mirror") ?? false);
  const title = resolvePageTitle(pathname, plugins?.getNavItems() ?? []);
  const subtitle =
    matchLongestPrefix(pathname, PAGE_SUBTITLES) ?? "Cognitive-aware learning hub";

  const barRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<HTMLDivElement>(null);
  const longPressRef = useRef<number | null>(null);

  const [rocketPass, setRocketPass] = useState(0);
  const [flight, setFlight] = useState<{ fromX: number; toX: number; y: number } | null>(null);

  const measureFlight = () => {
    const bar = barRef.current;
    const title = titleRef.current;
    const timer = timerRef.current;
    if (!bar || !title || !timer) return null;
    const br = bar.getBoundingClientRect();
    const tr = title.getBoundingClientRect();
    const tm = timer.getBoundingClientRect();
    const rocketW = 28;
    const fromX = Math.max(0, tr.right - br.left - 2);
    const toX = Math.max(fromX + 40, tm.left - br.left - rocketW * 0.35);
    const y = br.height / 2 - 7;
    return { fromX, toX, y };
  };

  const launchRocket = () => {
    const path = measureFlight();
    if (!path) return;
    setFlight(path);
    setRocketPass((n) => n + 1);
  };

  const clearLongPress = () => {
    if (longPressRef.current != null) {
      window.clearTimeout(longPressRef.current);
      longPressRef.current = null;
    }
  };

  const onTitlePointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    clearLongPress();
    longPressRef.current = window.setTimeout(() => {
      longPressRef.current = null;
      launchRocket();
    }, LONG_PRESS_MS);
  };

  return (
    <header className="gloss-topbar sticky top-0 z-40 min-h-16 h-16 shrink-0 overflow-visible">
      <div ref={barRef} className="relative flex h-full items-center justify-between gap-6 px-5">
        <AnimatePresence>
          {rocketPass > 0 && flight ? (
            <motion.div
              key={rocketPass}
              className="pointer-events-none absolute z-20 flex items-center"
              style={{ top: flight.y, left: 0 }}
              initial={{ x: flight.fromX, opacity: 0 }}
              animate={{
                x: [flight.fromX, flight.fromX + 4, flight.toX],
                opacity: [0, 1, 1, 0],
              }}
              exit={{ opacity: 0 }}
              transition={{
                duration: 2.2,
                times: [0, 0.22, 1],
                ease: ["easeOut", [0.15, 0.05, 0.2, 1]],
                opacity: { duration: 2.2, times: [0, 0.1, 0.85, 1] },
              }}
            >
              <motion.span
                className="mr-0.5 block h-[3px] rounded-full"
                style={{
                  background: `linear-gradient(90deg, transparent 0%, ${ROCKET_COLOR}88 55%, #fff 100%)`,
                  boxShadow: `0 0 10px ${ROCKET_COLOR}`,
                }}
                initial={{ width: 6, opacity: 0 }}
                animate={{ width: [6, 22, 26], opacity: [0, 1, 0.85] }}
                transition={{ duration: 1.6, times: [0, 0.3, 1] }}
              />
              <FlatRocket
                color={ROCKET_COLOR}
                className="drop-shadow-[0_0_10px_rgba(251,146,60,0.95)]"
              />
            </motion.div>
          ) : null}
        </AnimatePresence>

        <div
          ref={titleRef}
          className="topbar-title-card relative z-10 min-w-0 cursor-pointer select-none"
          onPointerDown={onTitlePointerDown}
          onPointerUp={clearLongPress}
          onPointerLeave={clearLongPress}
          onPointerCancel={clearLongPress}
          title="Long-press for a surprise…"
        >
          <h1 className="topbar-title-card__heading" data-text={title}>
            {title}
          </h1>
          <p className="topbar-title-card__sub hidden sm:block">{subtitle}</p>
        </div>

        <div className="relative z-10 flex items-center gap-3">
          <DashboardChromeDock />
          {focusMirrorOn && <FaceTrackerDock />}
          <div ref={timerRef} className="inline-flex">
            <PomodoroDock />
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="gloss-dock-btn rounded-full p-2 hover:scale-105 transition-transform"
                aria-label="Account menu"
                title={isAuthenticated ? user?.username : "Login"}
              >
                <CircleUserRound className="w-5 h-5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuLabel>
                {isAuthenticated ? `Signed in: ${user?.username}` : "Account"}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {!isAuthenticated ? (
                <DropdownMenuItem onClick={() => nav("/login")}>
                  <LogIn className="w-4 h-4 mr-2" />
                  Login / Register
                </DropdownMenuItem>
              ) : (
                <>
                  <DropdownMenuItem onClick={() => nav("/profile")}>
                    <CircleUserRound className="w-4 h-4 mr-2" />
                    Profile
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => nav("/settings/plugins")}>Plugins & features</DropdownMenuItem>
                  {isAdmin && (
                    <DropdownMenuItem onClick={() => nav("/admin")}>
                      <Shield className="w-4 h-4 mr-2" />
                      Admin Panel
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    variant="destructive"
                    onClick={() => {
                      logout();
                      nav("/");
                    }}
                  >
                    <LogOut className="w-4 h-4 mr-2" />
                    Logout
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
          <ThemeToggle size="sm" />
        </div>
      </div>
    </header>
  );
}
