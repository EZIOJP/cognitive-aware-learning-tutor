import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { useLocation, useNavigate } from "react-router";
import { CircleUserRound, Shield } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { ThemeToggle } from "../components/theme/ThemeToggle";
import { useAuth } from "../context/AuthContext";
import { PomodoroDock } from "./topbar/PomodoroDock";
import { FaceTrackerDock } from "./topbar/FaceTrackerDock";
import { DashboardChromeDock } from "./topbar/DashboardChromeDock";
import { usePluginsOptional } from "../plugins/registry";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../app/components/ui/dropdown-menu";
import { matchLongestPrefix, PAGE_SUBTITLES, resolvePageTitle } from "./pageTitles";

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

/** Plan: Study top bar = profile, theme, pomodoro. Focus shell moves chrome into the sidebar. */
export function AppTopBar() {
  const nav = useNavigate();
  const { pathname } = useLocation();
  const { user, isAuthenticated, isAdmin } = useAuth();
  const plugins = usePluginsOptional();
  const focusShell = isFocusDesktopShell();
  const focusMirrorOn =
    Boolean(plugins?.isLoaded) && (plugins?.enabledIds.includes("focus-mirror") ?? false);
  const title = resolvePageTitle(pathname, plugins?.getNavItems() ?? []);
  const subtitle = matchLongestPrefix(pathname, PAGE_SUBTITLES) ?? "Cognitive-aware learning hub";

  const barRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<HTMLDivElement>(null);
  const longPressRef = useRef<number | null>(null);

  const [rocketPass, setRocketPass] = useState(0);
  const [flight, setFlight] = useState<{ fromX: number; toX: number; y: number } | null>(null);

  /* Focus: page title lives in the sidebar brand row. */
  if (focusShell) return null;

  const measureFlight = () => {
    const bar = barRef.current;
    const titleEl = titleRef.current;
    const timer = timerRef.current;
    if (!bar || !titleEl || !timer) return null;
    const br = bar.getBoundingClientRect();
    const tr = titleEl.getBoundingClientRect();
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
          {subtitle ? (
            <p className="topbar-title-card__sub hidden sm:block">{subtitle}</p>
          ) : null}
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
                title={isAuthenticated ? (user?.display_name || user?.username) : "Profile"}
              >
                <CircleUserRound className="w-5 h-5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuLabel>
                {isAuthenticated
                  ? user?.display_name || user?.username || "Owner"
                  : "This machine"}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
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
            </DropdownMenuContent>
          </DropdownMenu>
          <ThemeToggle size="sm" />
        </div>
      </div>
    </header>
  );
}
