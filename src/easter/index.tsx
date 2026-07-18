import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";

type Burst = {
  id: number;
  kind: "confetti" | "pi" | "fireworks" | "avocado" | "words" | "glow" | "bounce" | "doodle" | "hat" | "cat";
  label?: string;
  x?: number;
  y?: number;
};

type EasterApi = {
  burst: (kind: Burst["kind"], label?: string, at?: { x: number; y: number }) => void;
};

const EasterCtx = createContext<EasterApi | null>(null);

export function useEaster(): EasterApi {
  const ctx = useContext(EasterCtx);
  if (!ctx) {
    return {
      burst: () => {
        /* no-op outside provider */
      },
    };
  }
  return ctx;
}

/** Count rapid taps; fires when reaching `need` within `windowMs`. */
export function useTapCombo(need: number, onFire: () => void, windowMs = 700) {
  const count = useRef(0);
  const last = useRef(0);
  return useCallback(() => {
    const now = Date.now();
    count.current = now - last.current > windowMs ? 1 : count.current + 1;
    last.current = now;
    if (count.current >= need) {
      count.current = 0;
      onFire();
    }
  }, [need, onFire, windowMs]);
}

export function useLongPress(ms: number, onFire: () => void) {
  const timer = useRef<number | null>(null);
  const clear = useCallback(() => {
    if (timer.current != null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);
  const onPointerDown = useCallback(
    (e: ReactPointerEvent) => {
      if (e.button !== 0) return;
      clear();
      timer.current = window.setTimeout(() => {
        timer.current = null;
        onFire();
      }, ms);
    },
    [clear, ms, onFire],
  );
  return {
    onPointerDown,
    onPointerUp: clear,
    onPointerLeave: clear,
    onPointerCancel: clear,
  };
}

const KONAMI = [
  "ArrowUp",
  "ArrowUp",
  "ArrowDown",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
  "ArrowLeft",
  "ArrowRight",
  "b",
  "a",
];

export function useKonami(onFire: () => void) {
  const idx = useRef(0);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      const expect = KONAMI[idx.current];
      if (key === expect || (expect.length === 1 && key === expect)) {
        idx.current += 1;
        if (idx.current >= KONAMI.length) {
          idx.current = 0;
          onFire();
        }
      } else {
        idx.current = key === KONAMI[0] ? 1 : 0;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onFire]);
}

/** Sequence of step ids clicked, e.g. [1,2,3,2,1] */
export function useStepDance(pattern: number[], onFire: () => void) {
  const buf = useRef<number[]>([]);
  return useCallback(
    (step: number) => {
      buf.current = [...buf.current, step].slice(-pattern.length);
      if (
        buf.current.length === pattern.length &&
        buf.current.every((v, i) => v === pattern[i])
      ) {
        buf.current = [];
        onFire();
      }
    },
    [pattern, onFire],
  );
}

function BurstLayer({ bursts }: { bursts: Burst[] }) {
  return createPortal(
    <div className="pointer-events-none fixed inset-0 z-[200] overflow-hidden">
      <AnimatePresence>
        {bursts.map((b) => (
          <BurstVisual key={b.id} burst={b} />
        ))}
      </AnimatePresence>
    </div>,
    document.body,
  );
}

function BurstVisual({ burst }: { burst: Burst }) {
  const cx = burst.x ?? window.innerWidth / 2;
  const cy = burst.y ?? window.innerHeight / 3;

  if (burst.kind === "glow") {
    return (
      <motion.div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(251,191,36,0.28) 0%, transparent 65%)",
        }}
        initial={{ opacity: 0 }}
        animate={{ opacity: [0, 1, 0] }}
        transition={{ duration: 2.2 }}
      />
    );
  }

  if (burst.kind === "bounce") {
    return (
      <motion.div
        className="absolute left-0 right-0 top-0 h-1 bg-primary"
        initial={{ scaleX: 0, opacity: 0 }}
        animate={{ scaleX: [0, 1, 1, 0], opacity: [0, 1, 1, 0], y: [0, 0, 8, 0] }}
        transition={{ duration: 1.4 }}
      />
    );
  }

  if (burst.kind === "hat") {
    return (
      <motion.div
        className="absolute text-4xl"
        style={{ left: cx, top: cy }}
        initial={{ y: 20, opacity: 0, rotate: -20 }}
        animate={{ y: [-10, -40], opacity: [0, 1, 0], rotate: [-20, 10, -5] }}
        transition={{ duration: 1.8 }}
      >
        🎩
      </motion.div>
    );
  }

  if (burst.kind === "cat") {
    return (
      <motion.div
        className="absolute text-2xl"
        style={{ top: Math.min(cy, window.innerHeight - 80) }}
        initial={{ x: -40, opacity: 0 }}
        animate={{ x: [ -40, window.innerWidth + 40], opacity: [0, 1, 1, 0] }}
        transition={{ duration: 3.2, ease: "linear", opacity: { times: [0, 0.1, 0.85, 1] } }}
      >
        🐈
      </motion.div>
    );
  }

  if (burst.kind === "doodle") {
    return (
      <motion.svg
        className="absolute"
        style={{ left: cx - 40, top: cy - 20 }}
        width="120"
        height="60"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ opacity: [0, 1, 1, 0] }}
        transition={{ duration: 2.5 }}
      >
        <motion.path
          d="M10 40 Q 40 5 70 35 T 110 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-primary"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.2 }}
        />
      </motion.svg>
    );
  }

  const glyphs =
    burst.kind === "pi"
      ? ["π", "π", "π", "π", "π", "π", "π", "π"]
      : burst.kind === "avocado"
        ? ["🥑", "🥑", "🥑", "🥑", "🥑", "🥑"]
        : burst.kind === "words" && burst.label
          ? Array.from({ length: 8 }, () => burst.label!)
          : burst.kind === "fireworks"
            ? ["✦", "✧", "★", "✦", "✧", "★", "✦", "✧"]
            : ["✦", "◆", "●", "▲", "✦", "◆", "●", "▲"];

  return (
    <>
      {glyphs.map((g, i) => {
        const ang = (i / glyphs.length) * Math.PI * 2;
        const dist = 60 + (i % 3) * 28;
        return (
          <motion.span
            key={`${burst.id}-${i}`}
            className="absolute text-sm font-semibold tabular-nums"
            style={{ left: cx, top: cy, color: burst.kind === "pi" ? "#a78bfa" : undefined }}
            initial={{ x: 0, y: 0, opacity: 0, scale: 0.6 }}
            animate={{
              x: Math.cos(ang) * dist,
              y: Math.sin(ang) * dist - 20,
              opacity: [0, 1, 0],
              scale: [0.6, 1.1, 0.8],
            }}
            transition={{ duration: 1.6, delay: i * 0.04, ease: "easeOut" }}
          >
            {g}
          </motion.span>
        );
      })}
    </>
  );
}

export function EasterProvider({ children }: { children: ReactNode }) {
  const [bursts, setBursts] = useState<Burst[]>([]);
  const burst = useCallback((kind: Burst["kind"], label?: string, at?: { x: number; y: number }) => {
    const id = Date.now() + Math.random();
    setBursts((prev) => [...prev, { id, kind, label, x: at?.x, y: at?.y }]);
    window.setTimeout(() => {
      setBursts((prev) => prev.filter((b) => b.id !== id));
    }, 2800);
  }, []);

  return (
    <EasterCtx.Provider value={{ burst }}>
      {children}
      <BurstLayer bursts={bursts} />
    </EasterCtx.Provider>
  );
}
