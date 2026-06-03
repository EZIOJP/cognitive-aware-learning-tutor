/**
 * Theme toggle — from refernces/theme toggole (ThemeToggleAdvanced)
 * Sun / Moon with sky gradient, stars, and clouds.
 */
import React, { useMemo } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Sun, Moon, Cloud, Star } from "lucide-react";
import { useTheme } from "../../context/ThemeContext";
import { useNavigate } from "react-router";

const SIZE = {
  sm: { button: 40, icon: 14 },
  md: { button: 56, icon: 16 },
  lg: { button: 72, icon: 20 },
};

type ThemeToggleSize = keyof typeof SIZE;

type ThemeToggleVariant = "animated" | "compact";

const VARIANT_KEY = "themeToggleVariant";

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
  const variant = variantProp ?? storedVariant;

  React.useEffect(() => {
    const onChange = () => setStoredVariant(readVariant());
    window.addEventListener("theme-toggle-variant", onChange);
    return () => window.removeEventListener("theme-toggle-variant", onChange);
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
    // Short click toggles theme
    toggleTheme();
  };


  const stars = useMemo(
    () =>
      Array.from({ length: 8 }, (_, i) => ({
        id: i,
        x: 12 + (i * 11) % 80,
        y: 10 + (i * 17) % 75,
        delay: (i % 5) * 0.1,
        scale: 0.6 + (i % 3) * 0.15,
      })),
    []
  );

  const clouds = useMemo(
    () => [
      { id: 1, x: 15, y: 20, size: 0.6, duration: 4, delay: 0 },
      { id: 2, x: 65, y: 35, size: 0.5, duration: 5, delay: 1 },
      { id: 3, x: 40, y: 65, size: 0.55, duration: 4.5, delay: 0.5 },
      { id: 4, x: 75, y: 70, size: 0.45, duration: 5.5, delay: 1.5 },
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
    return (
      <button
        type="button"
        onClick={handleClick}
        className={`${className} relative rounded-full p-0.5 focus:outline-none focus:ring-2 focus:ring-ring shrink-0 transition-colors ${
          isDarkMode
            ? "bg-gradient-to-r from-blue-600 to-purple-600"
            : "bg-gradient-to-r from-amber-400 to-orange-500"
        }`}
        style={{ width: trackW, height: trackH }}
        aria-label={`Switch to ${isDarkMode ? "light" : "dark"} mode`}
      >
        <motion.div
          className="absolute top-0.5 left-0.5 rounded-full bg-white shadow flex items-center justify-center"
          style={{ width: thumb, height: thumb }}
          animate={{ x: isDarkMode ? trackW - thumb - 6 : 0 }}
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
        >
          <motion.div
            key={isDarkMode ? "moon" : "sun"}
            initial={{ rotate: -90, opacity: 0 }}
            animate={{ rotate: 0, opacity: 1 }}
            transition={{ duration: 0.25 }}
          >
            {isDarkMode ? (
              <Moon size={thumb - 8} className="text-slate-700" />
            ) : (
              <Sun size={thumb - 8} className="text-amber-500" />
            )}
          </motion.div>
        </motion.div>
      </button>
    );
  }

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
            ? "radial-gradient(circle at 30% 30%, #1e3a5f 0%, #0f172a 50%, #020617 100%)"
            : "radial-gradient(circle at 30% 30%, #60a5fa 0%, #3b82f6 40%, #2563eb 100%)",
        }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      />

      <AnimatePresence>
        {isDarkMode &&
          stars.map((star) => (
            <motion.div
              key={star.id}
              className="absolute"
              style={{ left: `${star.x}%`, top: `${star.y}%` }}
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: [0, 1, 0.7, 1], scale: star.scale }}
              exit={{ opacity: 0, scale: 0 }}
              transition={{
                duration: 1.2,
                delay: star.delay,
                opacity: {
                  repeat: Infinity,
                  repeatType: "reverse",
                  duration: 2.5,
                },
              }}
            >
              <Star size={3} fill="white" color="white" />
            </motion.div>
          ))}
      </AnimatePresence>

      <AnimatePresence>
        {!isDarkMode &&
          clouds.map((cloud) => (
            <motion.div
              key={cloud.id}
              className="absolute"
              style={{ right: `${cloud.x}%`, top: `${cloud.y}%` }}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: [0.3, 0.5, 0.3], x: [0, 5, 0] }}
              exit={{ opacity: 0, x: 10 }}
              transition={{
                opacity: {
                  repeat: Infinity,
                  duration: cloud.duration,
                  delay: cloud.delay,
                },
                x: {
                  repeat: Infinity,
                  duration: cloud.duration,
                  delay: cloud.delay,
                },
              }}
            >
              <Cloud
                size={s.icon * cloud.size}
                color="white"
                fill="white"
                opacity={0.4}
                strokeWidth={2}
              />
            </motion.div>
          ))}
      </AnimatePresence>

      <motion.div
        className="relative z-10 flex items-center justify-center"
        style={{ width: s.icon, height: s.icon }}
        animate={{ y: isDarkMode ? 2 : -2 }}
        transition={{ type: "spring", stiffness: 300, damping: 20 }}
      >
        <motion.div
          className="absolute inset-0 flex items-center justify-center"
          animate={{
            opacity: isDarkMode ? 0 : 1,
            scale: isDarkMode ? 0.3 : 1,
            rotate: isDarkMode ? -180 : 0,
          }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <Sun size={s.icon} color="#FCD34D" fill="#FCD34D" strokeWidth={2.5} />
          <motion.div
            className="absolute inset-0 rounded-full pointer-events-none"
            style={{
              background:
                "radial-gradient(circle, rgba(252, 211, 77, 0.5) 0%, transparent 70%)",
              filter: "blur(8px)",
            }}
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
          />
        </motion.div>

        <motion.div
          className="absolute inset-0 flex items-center justify-center"
          animate={{
            opacity: isDarkMode ? 1 : 0,
            scale: isDarkMode ? 1 : 0.3,
            rotate: isDarkMode ? 0 : 180,
          }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <Moon size={s.icon} color="#FEF3C7" strokeWidth={2.5} fill="#FEF3C7" />
          <motion.div
            className="absolute inset-0 rounded-full pointer-events-none"
            style={{
              background:
                "radial-gradient(circle, rgba(254, 243, 199, 0.3) 0%, transparent 70%)",
              filter: "blur(6px)",
            }}
            animate={{ opacity: [0.5, 0.8, 0.5] }}
            transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
          />
        </motion.div>
      </motion.div>

      <motion.div
        className="absolute inset-0 rounded-full pointer-events-none"
        animate={{
          boxShadow: isDarkMode
            ? "0 0 0 1px rgba(148, 163, 184, 0.2), 0 0 20px rgba(59, 130, 246, 0.3), 0 8px 16px rgba(0, 0, 0, 0.4)"
            : "0 0 0 1px rgba(251, 191, 36, 0.3), 0 0 20px rgba(251, 191, 36, 0.4), 0 8px 16px rgba(251, 191, 36, 0.2)",
        }}
        transition={{ duration: 0.5 }}
      />
    </button>
  );
}
