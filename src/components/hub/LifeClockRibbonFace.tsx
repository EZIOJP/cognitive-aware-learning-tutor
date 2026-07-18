import { Suspense, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { cn } from "../../app/components/ui/utils";

export type RibbonActivity = {
  type: string;
  label: string;
  startHour: number;
  endHour: number;
  color: string;
  isProductive: boolean;
};

type LifeClockRibbonFaceProps = {
  size: number;
  compact?: boolean;
  activities: RibbonActivity[];
  currentHour: number;
  timeLeftHours: number;
  focusShare: number;
  clockLabel: string;
  showFocus?: boolean;
  productiveMinutes?: number;
  dayLabel?: string;
};

const MOTTO = "what you do is what you become";

function colorAtHour(activities: RibbonActivity[], hour: number): string {
  for (const a of activities) {
    if (a.type === "remaining") continue;
    if (hour >= a.startHour && hour < a.endHour) return a.color;
  }
  return "#1e293b";
}

/** Smooth S-curve path for the day ribbon (0 → 1 = midnight → midnight). */
function ribbonPoint(t: number): THREE.Vector3 {
  const u = Math.max(0, Math.min(1, t));
  const x = (u - 0.5) * 2.4;
  const y = Math.sin(u * Math.PI) * 0.55 - 0.15;
  const z = Math.cos(u * Math.PI * 1.15) * 0.75;
  return new THREE.Vector3(x, y, z);
}

function fullDayCurve(): THREE.CatmullRomCurve3 {
  return new THREE.CatmullRomCurve3(
    Array.from({ length: 64 }, (_, i) => ribbonPoint(i / 63)),
    false,
    "catmullrom",
    0.35,
  );
}

/** Continuous litmus-colored tube segments along the ribbon. */
function LitmusRibbonSegments({
  activities,
  currentHour,
}: {
  activities: RibbonActivity[];
  currentHour: number;
}) {
  const segments = useMemo(() => {
    const segs: { geom: THREE.TubeGeometry; color: string; opacity: number }[] = [];
    const usable = activities.filter((a) => a.type !== "remaining" && a.endHour > a.startHour);
    const source =
      usable.length > 0
        ? usable
        : [{ type: "elapsed", startHour: 0, endHour: Math.max(0.1, currentHour), color: "#475569" }];

    const build = (ta: number, tb: number, color: string, opacity: number) => {
      if (tb - ta < 0.002) return;
      const steps = Math.max(6, Math.ceil((tb - ta) * 80));
      const pts: THREE.Vector3[] = [];
      for (let i = 0; i <= steps; i++) {
        pts.push(ribbonPoint(ta + ((tb - ta) * i) / steps));
      }
      const curve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.4);
      segs.push({
        geom: new THREE.TubeGeometry(curve, steps * 2, 0.078, 12, false),
        color,
        opacity,
      });
    };

    for (const a of source) {
      const start = Math.max(0, a.startHour);
      const end = Math.min(24, a.endHour);
      if (end <= start) continue;
      const t0 = start / 24;
      const t1 = end / 24;
      const midCut = Math.min(t1, currentHour / 24);

      if (start >= currentHour) {
        build(t0, t1, a.color, 0.18);
      } else {
        build(t0, Math.min(t1, midCut), a.color, 1);
        if (t1 > midCut) build(midCut, t1, a.color, 0.18);
      }
    }
    return segs;
  }, [activities, currentHour]);

  return (
    <>
      {segments.map((s, i) => (
        <mesh key={i} geometry={s.geom}>
          <meshStandardMaterial
            color={s.color}
            emissive={s.color}
            emissiveIntensity={s.opacity > 0.5 ? 0.28 : 0.04}
            metalness={0.5}
            roughness={0.28}
            transparent
            opacity={s.opacity}
          />
        </mesh>
      ))}
    </>
  );
}

function RibbonScene({
  activities,
  currentHour,
}: {
  activities: RibbonActivity[];
  currentHour: number;
}) {
  const group = useRef<THREE.Group>(null);
  const progress = Math.max(0.02, Math.min(1, currentHour / 24));
  const guideCurve = useMemo(() => fullDayCurve(), []);

  useFrame((_, dt) => {
    if (group.current) group.current.rotation.y += dt * 0.18;
  });

  return (
    <>
      <color attach="background" args={["#050505"]} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[3, 4, 5]} intensity={1.2} color="#f8fafc" />
      <pointLight position={[2, 1, 3]} intensity={1} color="#67e8f9" />
      <pointLight position={[-2, -1, 2]} intensity={0.45} color="#a78bfa" />

      <group ref={group} rotation={[0.4, 0.35, -0.12]}>
        <mesh>
          <tubeGeometry args={[guideCurve, 120, 0.095, 14, false]} />
          <meshStandardMaterial color="#0f172a" metalness={0.4} roughness={0.45} transparent opacity={0.9} />
        </mesh>

        <LitmusRibbonSegments activities={activities} currentHour={currentHour} />

        <mesh position={ribbonPoint(progress)}>
          <sphereGeometry args={[0.1, 20, 20]} />
          <meshStandardMaterial color="#fff" emissive="#e2e8f0" emissiveIntensity={0.5} />
        </mesh>
      </group>
    </>
  );
}

function TickRing() {
  return (
    <svg className="pointer-events-none absolute inset-0 w-full h-full" viewBox="0 0 100 100" aria-hidden>
      {Array.from({ length: 60 }, (_, i) => {
        const a = (i / 60) * Math.PI * 2 - Math.PI / 2;
        const major = i % 5 === 0;
        return (
          <line
            key={i}
            x1={50 + Math.cos(a) * (major ? 46.1 : 47)}
            y1={50 + Math.sin(a) * (major ? 46.1 : 47)}
            x2={50 + Math.cos(a) * 48.5}
            y2={50 + Math.sin(a) * 48.5}
            stroke="rgba(226,232,240,0.4)"
            strokeWidth={major ? 0.4 : 0.2}
            strokeLinecap="round"
          />
        );
      })}
    </svg>
  );
}

export function LifeClockRibbonFace({
  size,
  compact = false,
  activities,
  currentHour,
  timeLeftHours,
  focusShare,
  clockLabel,
  showFocus = true,
  productiveMinutes = 0,
  dayLabel,
}: LifeClockRibbonFaceProps) {
  const prodLabel =
    productiveMinutes >= 60
      ? `${(productiveMinutes / 60).toFixed(1)}h`
      : `${productiveMinutes}m`;

  return (
    <div
      className="relative shrink-0 overflow-hidden rounded-full border border-white/10 bg-[#050505]"
      style={{ width: size, height: size }}
    >
      <Suspense
        fallback={
          <div className="absolute inset-0 flex items-center justify-center text-[10px] text-slate-400">
            Loading ribbon…
          </div>
        }
      >
        <Canvas
          dpr={[1, 1.75]}
          gl={{ antialias: true, alpha: false }}
          camera={{ position: [0, 0.2, 3.6], fov: 40 }}
          style={{ width: "100%", height: "100%" }}
        >
          <RibbonScene activities={activities} currentHour={currentHour} />
        </Canvas>
      </Suspense>

      {!compact && <TickRing />}

      <div className="pointer-events-none absolute inset-0 text-white drop-shadow-[0_1px_3px_rgba(0,0,0,0.95)]">
        {!compact && (
          <div className="absolute top-[11%] left-[12%] right-[12%] flex justify-between text-[8px] font-mono text-slate-300/90">
            <span>
              {prodLabel} <span className="text-slate-500">done</span>
            </span>
            <span>{Math.round((currentHour / 24) * 100)}%</span>
          </div>
        )}

        <div className={cn("absolute left-[11%]", compact ? "top-[28%]" : "top-[30%]")}>
          <p
            className={cn(
              "font-mono font-semibold tabular-nums leading-none",
              compact ? "text-base" : "text-[1.7rem]",
            )}
          >
            {clockLabel}
          </p>
          {!compact && dayLabel && (
            <p className="mt-1 text-[9px] uppercase tracking-[0.12em] text-slate-400">{dayLabel}</p>
          )}
          {!compact && (
            <p className="mt-0.5 text-[9px] font-mono text-sky-300/80">{timeLeftHours.toFixed(1)}h left</p>
          )}
        </div>

        {showFocus && (
          <div className={cn("absolute right-[10%] text-right", compact ? "top-[36%]" : "top-[38%]")}>
            <p className={cn("font-mono tabular-nums text-slate-200", compact ? "text-sm" : "text-lg")}>
              {focusShare}%
            </p>
            {!compact && (
              <p className="text-[8px] uppercase tracking-[0.14em] text-slate-500">focus</p>
            )}
          </div>
        )}

        {!compact && (
          <p className="absolute bottom-[10%] left-[10%] right-[10%] text-center text-[8px] italic text-slate-400/90">
            {MOTTO}
          </p>
        )}
      </div>
    </div>
  );
}
