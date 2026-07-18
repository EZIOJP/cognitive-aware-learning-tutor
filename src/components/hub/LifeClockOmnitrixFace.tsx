import { useId } from "react";
import { motion } from "motion/react";
import { cn } from "../../app/components/ui/utils";

export type OmnitrixActivity = {
  type: string;
  label: string;
  startHour: number;
  endHour: number;
  color: string;
  isProductive: boolean;
};

type LifeClockOmnitrixFaceProps = {
  size: number;
  compact?: boolean;
  activities: OmnitrixActivity[];
  currentHour: number;
  timeLeftHours: number;
  focusShare: number;
  clockLabel: string;
  showFocus?: boolean;
};

const CX = 50;
const CY = 50;
const R = 42;

/**
 * Classic Omnitrix dial geometry (matches the green/black reference):
 * four circle points ≈ NW, NE, SE, SW — hourglass = top+bottom lobes,
 * black wings = left+right. All tips meet at center.
 */
const HG = {
  // Angles in degrees (0° = east, CCW) — classic X on a clock face
  TL: 210, // top-left on rim
  TR: 330, // top-right
  BR: 30, // bottom-right
  BL: 150, // bottom-left
} as const;

function circlePoint(deg: number): { x: number; y: number } {
  const a = (deg * Math.PI) / 180;
  return { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a) };
}

function pts() {
  return {
    TL: circlePoint(HG.TL),
    TR: circlePoint(HG.TR),
    BR: circlePoint(HG.BR),
    BL: circlePoint(HG.BL),
  };
}

/** Green hourglass: top triangle + bottom triangle, tips at center. */
function hourglassPath(): string {
  const { TL, TR, BR, BL } = pts();
  return [
    // Top lobe (rim arc through 12 o'clock)
    `M ${TL.x} ${TL.y}`,
    `A ${R} ${R} 0 0 1 ${TR.x} ${TR.y}`,
    `L ${CX} ${CY}`,
    "Z",
    // Bottom lobe (rim arc through 6 o'clock)
    `M ${BR.x} ${BR.y}`,
    `A ${R} ${R} 0 0 1 ${BL.x} ${BL.y}`,
    `L ${CX} ${CY}`,
    "Z",
  ].join(" ");
}

/** Only the four diagonal edges (no green stroke on top/bottom arcs). */
function diagonalPaths(): string[] {
  const { TL, TR, BR, BL } = pts();
  return [
    `M ${TL.x} ${TL.y} L ${CX} ${CY}`,
    `M ${TR.x} ${TR.y} L ${CX} ${CY}`,
    `M ${BL.x} ${BL.y} L ${CX} ${CY}`,
    `M ${BR.x} ${BR.y} L ${CX} ${CY}`,
  ];
}

function faceCirclePath(): string {
  return `M ${CX} ${CY - R} A ${R} ${R} 0 1 1 ${CX} ${CY + R} A ${R} ${R} 0 1 1 ${CX} ${CY - R} Z`;
}

function hourToY(hour: number): number {
  const t = Math.max(0, Math.min(24, hour)) / 24;
  return CY - R + t * (2 * R);
}

export function LifeClockOmnitrixFace({
  size,
  compact = false,
  activities,
  currentHour,
  timeLeftHours,
  focusShare,
  clockLabel,
  showFocus = true,
}: LifeClockOmnitrixFaceProps) {
  const uid = useId().replace(/:/g, "");
  const hgClipId = `omni-hg-${uid}`;
  const faceClipId = `omni-face-${uid}`;
  const glowId = `omni-glow-${uid}`;
  const insetId = `omni-inset-${uid}`;
  const rimId = `omni-rim-${uid}`;
  const rimHiId = `omni-rim-hi-${uid}`;
  const wellId = `omni-well-${uid}`;
  const wingId = `omni-wing-${uid}`;
  const glassId = `omni-glass-${uid}`;
  const nowY = hourToY(currentHour);
  const hg = hourglassPath();
  const diagonals = diagonalPaths();
  const face = faceCirclePath();

  const pourSegments = activities.filter((a) => {
    if (["remaining", "idle", "elapsed"].includes(a.type)) return false;
    return a.endHour > a.startHour;
  });

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 100 100"
        className="w-full h-full drop-shadow-[0_14px_28px_rgba(0,0,0,0.55)]"
        role="img"
        aria-label="Omnitrix life dial — green hourglass is tracker pour"
      >
        <defs>
          <clipPath id={faceClipId}>
            <circle cx={CX} cy={CY} r={R} />
          </clipPath>
          <clipPath id={hgClipId}>
            <path d={hg} />
          </clipPath>
          <filter id={glowId} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="0.4" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id={insetId} x="-20%" y="-20%" width="140%" height="140%">
            <feOffset dx="0" dy="1.2" />
            <feGaussianBlur stdDeviation="1.4" result="offset-blur" />
            <feComposite operator="out" in="SourceGraphic" in2="offset-blur" result="inverse" />
            <feFlood floodColor="#000" floodOpacity="0.55" result="color" />
            <feComposite operator="in" in="color" in2="inverse" result="shadow" />
            <feComposite operator="over" in="shadow" in2="SourceGraphic" />
          </filter>
          <linearGradient id={rimId} x1="18%" y1="0%" x2="82%" y2="100%">
            <stop offset="0%" stopColor="#e4e4e7" />
            <stop offset="22%" stopColor="#a1a1aa" />
            <stop offset="48%" stopColor="#3f3f46" />
            <stop offset="72%" stopColor="#71717a" />
            <stop offset="100%" stopColor="#27272a" />
          </linearGradient>
          <linearGradient id={rimHiId} x1="30%" y1="0%" x2="70%" y2="40%">
            <stop offset="0%" stopColor="#fff" stopOpacity="0.5" />
            <stop offset="55%" stopColor="#fff" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <radialGradient id={wellId} cx="42%" cy="32%" r="75%">
            <stop offset="0%" stopColor="#14532d" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#020617" />
          </radialGradient>
          <radialGradient id={wingId} cx="50%" cy="40%" r="80%">
            <stop offset="0%" stopColor="#18181b" />
            <stop offset="100%" stopColor="#09090b" />
          </radialGradient>
          <linearGradient id={glassId} x1="50%" y1="8%" x2="50%" y2="55%">
            <stop offset="0%" stopColor="#fff" stopOpacity="0.1" />
            <stop offset="100%" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
        </defs>

        <circle cx={CX} cy={CY} r="48.8" fill={`url(#${rimId})`} />
        <circle cx={CX} cy={CY} r="47.4" fill="#18181b" />
        <circle cx={CX} cy={CY} r="46.4" fill={`url(#${rimId})`} />
        <circle cx={CX} cy={CY} r="46.4" fill="none" stroke={`url(#${rimHiId})`} strokeWidth="1.6" />
        <circle cx={CX} cy={CY} r="44.6" fill="#09090b" />

        <circle cx={CX} cy={CY} r={R} fill="#050505" filter={`url(#${insetId})`} />

        <g clipPath={`url(#${faceClipId})`}>
          {/* Black left/right triangles (evenodd punch) */}
          <path d={`${face} ${hg}`} fill={`url(#${wingId})`} fillRule="evenodd" />

          {/* Green hourglass well — subtle, data paints on top */}
          <path d={hg} fill={`url(#${wellId})`} />

          <g clipPath={`url(#${hgClipId})`}>
            {currentHour > 0.05 && (
              <rect
                x={CX - R}
                y={CY - R}
                width={R * 2}
                height={Math.max(0, nowY - (CY - R))}
                fill="rgba(148,163,184,0.06)"
              />
            )}
            {pourSegments.map((a, idx) => {
              const start = Math.max(0, a.startHour);
              const end = Math.min(24, a.endHour);
              if (end <= start) return null;
              const y1 = hourToY(start);
              const y2 = hourToY(end);
              const h = Math.max(0.4, y2 - y1);
              const past = end <= currentHour + 0.01;
              const ongoing = start < currentHour && end > currentHour;
              return (
                <motion.rect
                  key={`${a.type}-${idx}-${start.toFixed(3)}`}
                  x={CX - R}
                  y={y1}
                  width={R * 2}
                  height={h}
                  fill={a.color}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: past || ongoing ? 0.9 : 0.22 }}
                  transition={{ duration: 0.28 }}
                >
                  <title>{`${a.label} ${start.toFixed(1)}–${end.toFixed(1)}h`}</title>
                </motion.rect>
              );
            })}
            <path d={hg} fill={`url(#${glassId})`} className="pointer-events-none" />
          </g>

          {/* Diagonals only — tips meet at center like the reference */}
          {diagonals.map((d, i) => (
            <path
              key={`omni-diag-${i}`}
              d={d}
              fill="none"
              stroke="#4ade80"
              strokeWidth={1.35}
              strokeLinecap="round"
              opacity={0.92}
              filter={`url(#${glowId})`}
            />
          ))}
          <circle cx={CX} cy={CY} r={1.2} fill="#4ade80" />
          <circle cx={CX} cy={CY} r={0.45} fill="#052e16" />
        </g>

        <circle
          cx={CX}
          cy={nowY}
          r={compact ? 1.4 : 1.85}
          fill="#f8fafc"
          stroke="#4ade80"
          strokeWidth="0.75"
        />
      </svg>

      <div
        className={cn(
          "pointer-events-none absolute top-1/2 -translate-y-1/2 flex flex-col items-center justify-center text-center",
          compact ? "left-[5%] w-[32%]" : "left-[4%] w-[34%]",
        )}
      >
        <span
          className={cn(
            "font-mono font-medium tabular-nums leading-none tracking-tight text-zinc-300/90",
            compact ? "text-[10px]" : "text-base sm:text-lg",
          )}
        >
          {clockLabel}
        </span>
        {!compact && (
          <span className="mt-1 text-[8px] font-mono tabular-nums text-zinc-500">
            {timeLeftHours.toFixed(1)}h left
          </span>
        )}
      </div>

      <div
        className={cn(
          "pointer-events-none absolute top-1/2 -translate-y-1/2 flex flex-col items-center justify-center text-center",
          compact ? "right-[5%] w-[32%]" : "right-[4%] w-[34%]",
        )}
      >
        {showFocus && (
          <span
            className={cn(
              "font-mono font-medium tabular-nums leading-none text-emerald-500/80",
              compact ? "text-[10px]" : "text-base sm:text-lg",
            )}
          >
            {focusShare}%
          </span>
        )}
        {!compact && (
          <span className="mt-1 text-[7px] uppercase tracking-[0.18em] text-zinc-600">focus</span>
        )}
      </div>
    </div>
  );
}
