/**
 * Theme toggle — from refernces/theme toggole (ThemeToggleAdvanced)
 * Sun / Moon with sky gradient, stars, and clouds.
 */
import React, { useMemo } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Sun } from "lucide-react";
import { useTheme } from "../../context/ThemeContext";
import { useNavigate } from "react-router";

/** Smooth crescent — two-circle mask anti-aliases better than Lucide Moon at small sizes. */
function SmoothMoon({
  size,
  color = "#FEF3C7",
  className = "",
}: {
  size: number;
  color?: string;
  className?: string;
}) {
  const maskId = React.useId().replace(/:/g, "");
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className}
      style={{ shapeRendering: "geometricPrecision" }}
      aria-hidden
    >
      <defs>
        <mask id={maskId}>
          <circle cx="12" cy="12" r="10" fill="#fff" />
          <circle cx="16.2" cy="9.2" r="8.6" fill="#000" />
        </mask>
      </defs>
      <circle cx="12" cy="12" r="10" fill={color} mask={`url(#${maskId})`} />
    </svg>
  );
}

const SIZE = {
  sm: { button: 40, icon: 14 },
  md: { button: 56, icon: 16 },
  lg: { button: 72, icon: 20 },
};

type ThemeToggleSize = keyof typeof SIZE;

type ThemeToggleVariant = "animated" | "compact";

const VARIANT_KEY = "themeToggleVariant";
const METEOR_EVENT = "theme-toggle:meteor-pass";

function readVariant(): ThemeToggleVariant {
  try {
    return localStorage.getItem(VARIANT_KEY) === "compact" ? "compact" : "animated";
  } catch {
    return "animated";
  }
}

interface ThemeToggleProps {
  className?: string;
  size?: ThemeToggleSize;
  /** Override stored variant (settings preview) */
  variant?: ThemeToggleVariant;
}

export function ThemeToggle({ className = "", size = "md", variant: variantProp }: ThemeToggleProps) {
  const { isDarkMode, toggleTheme, isLoading } = useTheme();
  const s = SIZE[size];
  const navigate = useNavigate();
  const [storedVariant, setStoredVariant] = React.useState<ThemeToggleVariant>(readVariant);
  const [meteorBurst, setMeteorBurst] = React.useState(0);
  const variant = variantProp ?? storedVariant;

  React.useEffect(() => {
    const onChange = () => setStoredVariant(readVariant());
    window.addEventListener("theme-toggle-variant", onChange);
    return () => window.removeEventListener("theme-toggle-variant", onChange);
  }, []);

  React.useEffect(() => {
    if (variant !== "animated" || isLoading) return undefined;
    const id = window.setInterval(() => setMeteorBurst((value) => value + 1), 90000);
    return () => window.clearInterval(id);
  }, [variant, isLoading]);

  React.useEffect(() => {
    const onMeteorPass = () => setMeteorBurst((value) => value + 1);
    window.addEventListener(METEOR_EVENT, onMeteorPass);
    return () => window.removeEventListener(METEOR_EVENT, onMeteorPass);
  }, []);
  // Long press handling
  const pressTimer = React.useRef<NodeJS.Timeout | null>(null);
  const handlePointerDown = () => {
    pressTimer.current = setTimeout(() => {
      // Navigate to theme settings on long press (~600ms)
      navigate("/settings/theme");
    }, 600);
  };
  const handlePointerUp = () => {
    if (pressTimer.current) {
      clearTimeout(pressTimer.current);
      pressTimer.current = null;
    }
  };
  const handleClick = () => {
    toggleTheme();
  };


  /** Shared slow orbital drift (seconds) — same for every star. */
  const STAR_DRIFT_S = 36;

  const stars = useMemo(
    () =>
      Array.from({ length: 8 }, (_, i) => ({
        id: i,
        // Start already on-screen so dark-first load shows stars immediately
        startAngle: -42 + ((i * 97) % 84),
        radiusPct: 0.58 + (i % 5) * 0.07,
        size: i % 3 === 0 ? 4.2 : i % 2 === 0 ? 3 : 2.2,
        delay: (i * 0.9) % 4.5,
        twinkleDelay: (i * 0.91) % 3.6,
        twinkleDuration: 2.6 + (i % 4) * 0.55,
      })),
    []
  );

  const clouds = useMemo(
    () => [
      { id: 1, x: 8, y: 16, scale: 0.42, duration: 16, delay: 0 },
      { id: 2, x: 68, y: 58, scale: 0.36, duration: 18, delay: 2.2 },
    ],
    []
  );

  if (isLoading) {
    return (
      <div
        className={`rounded-full bg-muted animate-pulse ${className}`}
        style={{ width: s.button, height: s.button }}
        aria-hidden
      />
    );
  }

  if (variant === "compact") {
    const trackW = size === "sm" ? 48 : size === "lg" ? 64 : 56;
    const trackH = size === "sm" ? 24 : size === "lg" ? 32 : 28;
    const thumb = size === "sm" ? 18 : size === "lg" ? 26 : 22;
    const thumbOffset = trackW - thumb - 4;
    return (
      <button
        type="button"
        onClick={handleClick}
        className={`${className} relative overflow-hidden rounded-full border border-white/15 p-0.5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.18),0_8px_22px_rgba(0,0,0,0.22)] focus:outline-none focus:ring-2 focus:ring-ring shrink-0`}
        style={{ width: trackW, height: trackH }}
        aria-label={`Switch to ${isDarkMode ? "light" : "dark"} mode`}
      >
        <motion.div
          className="absolute inset-0"
          animate={{
            background: isDarkMode
              ? "linear-gradient(135deg, #020617 0%, #111827 48%, #312e81 100%)"
              : "linear-gradient(135deg, #38bdf8 0%, #60a5fa 42%, #fbbf24 100%)",
          }}
          transition={{ duration: 0.45 }}
        />
        <motion.div
          className="absolute inset-x-1 top-1 h-2 rounded-full bg-white/25 blur-[1px]"
          animate={{ opacity: isDarkMode ? 0.12 : 0.35 }}
        />
        <AnimatePresence>
          {isDarkMode ? (
            <motion.div
              key="compact-stars"
              className="absolute inset-0"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <span className="absolute left-2 top-2 h-0.5 w-0.5 rounded-full bg-white/90" />
              <span className="absolute left-5 top-1.5 h-1 w-1 rounded-full bg-white/70" />
              <span className="absolute right-5 bottom-2 h-0.5 w-0.5 rounded-full bg-white/80" />
            </motion.div>
          ) : (
            <motion.div
              key="compact-clouds"
              className="absolute inset-0"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <span className="absolute left-2 bottom-1.5 h-2 w-5 rounded-full bg-white/35 blur-[0.5px]" />
              <span className="absolute right-3 top-2 h-1.5 w-4 rounded-full bg-white/30 blur-[0.5px]" />
            </motion.div>
          )}
        </AnimatePresence>
        <motion.div
          className="absolute left-0.5 top-0.5 rounded-full border border-white/30 shadow-[0_4px_10px_rgba(0,0,0,0.28)] flex items-center justify-center"
          animate={{
            x: isDarkMode ? thumbOffset : 0,
            background: isDarkMode
              ? "linear-gradient(135deg, rgba(199,210,254,0.95), rgba(129,140,248,0.72))"
              : "linear-gradient(135deg, rgba(255,255,255,0.95), rgba(255,255,255,0.65))",
          }}
          style={{ width: thumb, height: thumb }}
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
        >
          <span className="absolute inset-1 rounded-full bg-white/30 blur-[1px]" />
          <motion.div
            key={isDarkMode ? "moon" : "sun"}
            className="relative"
            initial={{ rotate: -90, opacity: 0 }}
            animate={{ rotate: 0, opacity: 1 }}
            transition={{ duration: 0.25 }}
          >
            {isDarkMode ? (
              <SmoothMoon size={thumb - 8} color="#0f172a" />
            ) : (
              <Sun size={thumb - 8} className="text-amber-500" fill="currentColor" />
            )}
          </motion.div>
        </motion.div>
      </button>
    );
  }

  const celestialSize = s.icon + (size === "sm" ? 3 : 6);

  return (
    <button
      type="button"
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerLeave={handlePointerUp}
      onClick={handleClick}
      className={`${className} relative rounded-full inline-flex items-center justify-center cursor-pointer group overflow-hidden shrink-0`}
      style={{
        width: s.button,
        height: s.button,
        border: "2px solid rgba(255, 255, 255, 0.2)"
      }}
      title={`Switch to ${isDarkMode ? "light" : "dark"} mode`}
      aria-label={`Switch to ${isDarkMode ? "light" : "dark"} mode`}
    >
      <motion.div
        className="absolute inset-0"
        animate={{
          background: isDarkMode
            ? "radial-gradient(circle at 50% 30%, #0f172a 0%, #020617 55%, #000000 100%)"
            : "radial-gradient(circle at 50% 32%, #fef3c7 0%, #60a5fa 38%, #2563eb 100%)",
        }}
        transition={{ duration: 1.6, ease: [0.33, 1, 0.68, 1] }}
      />

      {/* Horizon + refined mountain ridges */}
      <motion.div
        className="absolute inset-x-0 bottom-0 h-[50%] pointer-events-none z-[2]"
        animate={{
          opacity: 1,
          background: isDarkMode
            ? "linear-gradient(to top, rgba(2,6,23,0.4), transparent 75%)"
            : "linear-gradient(to top, rgba(251,146,60,0.5), rgba(253,224,71,0.18), transparent 75%)",
        }}
        transition={{ duration: 1.6, ease: [0.33, 1, 0.68, 1] }}
      />
      <svg
        className="absolute inset-x-0 bottom-0 z-[3] h-[38%] w-full pointer-events-none"
        viewBox="0 0 100 40"
        preserveAspectRatio="none"
        aria-hidden
      >
        {/* Far range — fill only, no stroke outlines */}
        <motion.path
          d="M0 40 V28 C8 22 14 16 22 20 C30 24 36 12 44 15 C52 18 58 10 66 14 C74 18 82 11 90 16 C95 19 98 22 100 24 V40 Z"
          stroke="none"
          animate={{ fill: isDarkMode ? "#243044" : "rgba(30,41,59,0.32)" }}
          transition={{ duration: 1.6, ease: [0.33, 1, 0.68, 1] }}
        />
        {/* Mid range */}
        <motion.path
          d="M0 40 V32 C10 27 18 23 26 27 C34 31 42 21 50 24 C58 27 66 22 74 26 C82 30 90 25 100 29 V40 Z"
          stroke="none"
          animate={{ fill: isDarkMode ? "#334155" : "rgba(30,41,59,0.24)" }}
          transition={{ duration: 1.6, ease: [0.33, 1, 0.68, 1] }}
        />
        {/* Near foothills */}
        <motion.path
          d="M0 40 V36 C16 33 32 35 48 33 C64 31 80 34 100 35 V40 Z"
          stroke="none"
          animate={{ fill: isDarkMode ? "#0f172a" : "rgba(15,23,42,0.28)" }}
          transition={{ duration: 1.6, ease: [0.33, 1, 0.68, 1] }}
        />
      </svg>

      {/* Tiny cloud wisps — keep sky readable */}
      <div className="absolute inset-0 z-[4] pointer-events-none overflow-hidden">
        {clouds.map((cloud) => (
          <motion.div
            key={cloud.id}
            className="absolute"
            style={{
              left: `${cloud.x}%`,
              top: `${cloud.y}%`,
              transform: `scale(${cloud.scale})`,
              transformOrigin: "left center",
            }}
            initial={false}
            animate={{
              opacity: isDarkMode ? [0.28, 0.4, 0.28] : [0.35, 0.5, 0.35],
              x: [0, 3, 0],
            }}
            transition={{
              opacity: {
                repeat: Infinity,
                duration: cloud.duration,
                delay: cloud.delay,
                ease: "easeInOut",
              },
              x: {
                repeat: Infinity,
                duration: cloud.duration,
                delay: cloud.delay,
                ease: "easeInOut",
              },
            }}
          >
            <span
              className="absolute rounded-full"
              style={{
                width: 7,
                height: 4,
                left: 0,
                top: 2,
                background: isDarkMode ? "rgba(148,163,184,0.5)" : "rgba(255,255,255,0.65)",
              }}
            />
            <span
              className="absolute rounded-full"
              style={{
                width: 5,
                height: 5,
                left: 3,
                top: 0,
                background: isDarkMode ? "rgba(203,213,225,0.45)" : "rgba(255,255,255,0.8)",
              }}
            />
            <span
              className="absolute rounded-full"
              style={{
                width: 6,
                height: 4,
                left: 6,
                top: 2,
                background: isDarkMode ? "rgba(148,163,184,0.4)" : "rgba(255,255,255,0.55)",
              }}
            />
          </motion.div>
        ))}
      </div>

      {/* Stars above clouds — visible immediately on dark-first load */}
      <div className="absolute inset-0 z-[6] pointer-events-none overflow-hidden">
        {stars.map((star) => {
          const radiusPx = s.button * star.radiusPct;
          const endAngle = star.startAngle + 96;
          return (
            <div
              key={star.id}
              className="absolute left-1/2 top-[118%] h-0 w-0"
              aria-hidden
            >
              <motion.div
                className="relative"
                initial={isDarkMode ? { rotate: star.startAngle } : { rotate: star.startAngle }}
                animate={
                  isDarkMode
                    ? { rotate: [star.startAngle, endAngle] }
                    : { rotate: star.startAngle }
                }
                transition={
                  isDarkMode
                    ? {
                        rotate: {
                          repeat: Infinity,
                          duration: STAR_DRIFT_S,
                          delay: star.delay,
                          ease: "linear",
                        },
                      }
                    : { duration: 0.35 }
                }
                style={{ transformOrigin: "0px 0px" }}
              >
                <motion.span
                  className="absolute"
                  style={{
                    left: 0,
                    top: -radiusPx,
                    width: star.size,
                    height: star.size,
                    marginLeft: -star.size / 2,
                  }}
                  initial={false}
                  animate={
                    isDarkMode
                      ? {
                          opacity: [0.55, 1, 0.6, 0.95, 0.55],
                          scale: [0.9, 1.2, 0.95, 1.15, 0.9],
                        }
                      : { opacity: 0, scale: 0.5 }
                  }
                  transition={
                    isDarkMode
                      ? {
                          repeat: Infinity,
                          duration: star.twinkleDuration,
                          delay: star.twinkleDelay,
                          ease: "easeInOut",
                        }
                      : { duration: 0.25 }
                  }
                >
                  <span
                    className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white"
                    style={{
                      width: Math.max(1.4, star.size * 0.32),
                      height: Math.max(1.4, star.size * 0.32),
                      boxShadow: `0 0 ${star.size}px rgba(255,255,255,0.95), 0 0 ${star.size * 2}px rgba(186,230,253,0.55)`,
                    }}
                  />
                  <span
                    className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-gradient-to-r from-transparent via-white to-transparent"
                    style={{ width: star.size, height: 1 }}
                  />
                  <span
                    className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-gradient-to-b from-transparent via-white to-transparent"
                    style={{ width: 1, height: star.size }}
                  />
                </motion.span>
              </motion.div>
            </div>
          );
        })}
      </div>

      <AnimatePresence>
        {meteorBurst > 0 ? (
          <motion.div
            key={meteorBurst}
            className="absolute left-0 top-1 z-[9] flex items-center pointer-events-none"
            initial={{ x: -30, y: -12, opacity: 0, rotate: 28 }}
            animate={{
              x: [-30, 10, 48, 58],
              y: [-12, 8, 26, 32],
              opacity: [0, 1, 1, 1, 0],
            }}
            exit={{ opacity: 0 }}
            transition={{
              duration: 3.6,
              ease: "linear",
              times: [0, 0.12, 0.62, 0.72, 1],
              opacity: { duration: 3.6, times: [0, 0.08, 0.7, 0.88, 1], ease: "easeOut" },
            }}
          >
            <div className="relative flex items-center">
              {/* Tail collapses into the head at the end (origin = head / right) */}
              <motion.span
                className="block h-px rounded-full"
                style={{
                  width: 44,
                  transformOrigin: "right center",
                  background:
                    "linear-gradient(90deg, transparent 0%, rgba(167,139,250,0.45) 35%, rgba(244,114,182,0.8) 72%, #fff 100%)",
                  boxShadow: "0 0 4px rgba(167,139,250,0.55), 0 0 5px rgba(125,211,252,0.35)",
                }}
                initial={{ scaleX: 0.15, opacity: 0 }}
                animate={{
                  scaleX: [0.15, 1, 1, 0],
                  opacity: [0, 1, 1, 0],
                }}
                transition={{
                  duration: 3.6,
                  times: [0, 0.14, 0.68, 0.82],
                  ease: ["easeOut", "linear", "easeIn"],
                }}
              />
              <motion.span
                className="-ml-0.5 relative h-1.5 w-1.5 rounded-full"
                style={{
                  background:
                    "radial-gradient(circle, #fff 0%, #fef3c7 40%, #f9a8d4 70%, #a78bfa 100%)",
                  boxShadow:
                    "0 0 4px #fff, 0 0 10px rgba(244,114,182,0.9), 0 0 14px rgba(167,139,250,0.7)",
                }}
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{
                  scale: [0.6, 1, 1, 1.7, 0.75, 1.55, 0.2],
                  opacity: [0, 1, 1, 1, 0.45, 1, 0],
                }}
                transition={{
                  duration: 3.6,
                  times: [0, 0.1, 0.68, 0.78, 0.85, 0.92, 1],
                  ease: "easeOut",
                }}
              />
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence mode="sync" initial={false}>
        {isDarkMode ? (
          <motion.div
            key="moon"
            className="absolute z-10 grid place-items-center rounded-full pointer-events-none"
            style={{
              width: celestialSize,
              height: celestialSize,
              left: "50%",
              top: "50%",
              marginLeft: -celestialSize / 2,
              marginTop: -celestialSize / 2,
            }}
            initial={{ opacity: 0, y: -28, scale: 0.75 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -28, scale: 0.8 }}
            transition={{ duration: 1.05, ease: [0.33, 1, 0.68, 1] }}
          >
            <motion.span
              className="absolute inset-0 rounded-full bg-indigo-200/25 blur-md"
              animate={{ opacity: [0.35, 0.7, 0.35], scale: [0.9, 1.16, 0.9] }}
              transition={{ repeat: Infinity, duration: 3.5, ease: "easeInOut" }}
            />
            <SmoothMoon size={celestialSize - 2} color="#FEF3C7" className="relative drop-shadow-[0_0_6px_rgba(254,243,199,0.45)]" />
          </motion.div>
        ) : (
          <motion.div
            key="sun"
            className="absolute z-10 grid place-items-center rounded-full pointer-events-none"
            style={{
              width: celestialSize,
              height: celestialSize,
              left: "50%",
              top: "50%",
              marginLeft: -celestialSize / 2,
              marginTop: -celestialSize / 2,
            }}
            initial={{ opacity: 0, y: 28, scale: 0.75 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 28, scale: 0.8 }}
            transition={{ duration: 1.05, ease: [0.33, 1, 0.68, 1] }}
          >
            <motion.span
              className="absolute inset-0 rounded-full bg-amber-300/40 blur-md"
              animate={{ opacity: [0.45, 0.85, 0.45], scale: [0.9, 1.2, 0.9] }}
              transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
            />
            <Sun size={celestialSize - 3} color="#FCD34D" fill="#FCD34D" strokeWidth={2.4} />
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        className="absolute inset-0 rounded-full pointer-events-none"
        animate={{
          boxShadow: isDarkMode
            ? "0 0 0 1px rgba(148, 163, 184, 0.2), 0 0 20px rgba(59, 130, 246, 0.3), 0 8px 16px rgba(0, 0, 0, 0.4)"
            : "0 0 0 1px rgba(251, 191, 36, 0.3), 0 0 20px rgba(251, 191, 36, 0.4), 0 8px 16px rgba(251, 191, 36, 0.2)",
        }}
        transition={{ duration: 1.2, ease: [0.33, 1, 0.68, 1] }}
      />
    </button>
  );
}
