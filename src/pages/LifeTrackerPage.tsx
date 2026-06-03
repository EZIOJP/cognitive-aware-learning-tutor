import { useState } from "react";
import { useGoalTracker, computeScores } from "../context/GoalTrackerContext";
import { DayTimeTracker } from "../features/math/components/DayTimeTracker";
import { Moon, Dumbbell, Droplets, Brain, Monitor, TreePine, Smile, Clock, CheckSquare, TrendingUp, ChevronDown, ChevronUp, Flame } from "lucide-react";
import { Card } from "../app/components/ui/card";

// ─────────────────────────────────────────────────────────
// Score ring component
// ─────────────────────────────────────────────────────────

function ScoreRing({ score, label, color }: { score: number; label: string; color: string }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-16 h-16">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 70 70">
          <circle cx="35" cy="35" r={r} fill="none" stroke="currentColor" strokeWidth="6" className="text-muted/30" />
          <circle
            cx="35" cy="35" r={r}
            fill="none"
            stroke={color}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circ}`}
            className="transition-all duration-700"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-sm font-bold">
          {score}
        </span>
      </div>
      <span className="text-xs text-muted-foreground text-center leading-tight">{label}</span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Input row
// ─────────────────────────────────────────────────────────

function InputRow({
  icon: Icon,
  label,
  value,
  min = 0,
  max = 100,
  step = 1,
  unit,
  onChange,
  isSlider = false,
}: {
  icon: any;
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  onChange: (v: number) => void;
  isSlider?: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <Icon className="w-4 h-4 text-muted-foreground shrink-0" />
      <span className="text-xs text-muted-foreground w-28 shrink-0">{label}</span>
      {isSlider ? (
        <div className="flex items-center gap-2 flex-1">
          <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            className="flex-1 accent-primary h-1"
          />
          <span className="text-xs font-medium w-10 text-right">{value}{unit}</span>
        </div>
      ) : (
        <div className="flex items-center gap-2 flex-1">
          <button
            onClick={() => onChange(Math.max(min, value - step))}
            className="w-6 h-6 rounded-full border border-border/50 text-sm flex items-center justify-center hover:bg-muted transition-colors"
          >−</button>
          <span className="text-sm font-semibold w-8 text-center">{value}</span>
          <button
            onClick={() => onChange(Math.min(max, value + step))}
            className="w-6 h-6 rounded-full border border-border/50 text-sm flex items-center justify-center hover:bg-muted transition-colors"
          >+</button>
          {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────

const PILLAR_COLORS: Record<string, string> = {
  Health: "#10b981",
  Productivity: "#6366f1",
  "Digital Wellbeing": "#f59e0b",
  Mental: "#ec4899",
};

export function LifeTrackerPage() {
  const { today, history, updateToday, lifeScore, breakdown } = useGoalTracker();
  const [expandedPillar, setExpandedPillar] = useState<string | null>("Health");

  const u = (key: keyof typeof today) => (val: number) =>
    updateToday({ [key]: val } as any);

  const scoreLabel =
    lifeScore >= 80 ? "Thriving 🌟" :
    lifeScore >= 60 ? "On Track ✨" :
    lifeScore >= 40 ? "Needs Attention 🌱" :
    "Rest & Reset 🌙";

  // 7-day trend
  const last7 = history.slice(-7);

  return (
    <div className="h-full overflow-y-auto space-y-6 max-w-3xl">
      <DayTimeTracker />

      {/* Header */}
      <div className="gloss-panel rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="relative w-20 h-20">
            <svg className="w-full h-full -rotate-90" viewBox="0 0 80 80">
              <circle cx="40" cy="40" r="34" fill="none" stroke="currentColor" strokeWidth="7" className="text-muted/30" />
              <circle
                cx="40" cy="40" r="34"
                fill="none"
                stroke={lifeScore >= 70 ? "#10b981" : lifeScore >= 45 ? "#f59e0b" : "#ef4444"}
                strokeWidth="7"
                strokeLinecap="round"
                strokeDasharray={`${(lifeScore / 100) * (2 * Math.PI * 34)} ${2 * Math.PI * 34}`}
                className="transition-all duration-1000"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-xl font-bold leading-none">{lifeScore}</span>
              <span className="text-[10px] text-muted-foreground">/ 100</span>
            </div>
          </div>
          <div>
            <h2 className="text-2xl font-semibold">Life Score</h2>
            <p className="text-muted-foreground text-sm">{scoreLabel}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
            </p>
          </div>
        </div>

        {/* Pillar rings */}
        <div className="flex gap-4 justify-around flex-wrap">
          {Object.entries(breakdown).map(([pillar, score]) => (
            <ScoreRing
              key={pillar}
              score={score}
              label={pillar}
              color={PILLAR_COLORS[pillar] || "#6366f1"}
            />
          ))}
        </div>
      </div>

      {/* 7-day trend */}
      {last7.length >= 2 && (
        <div className="gloss-panel rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium">7-Day Life Score Trend</span>
          </div>
          <div className="flex items-end gap-1 h-12">
            {last7.map((entry) => {
              const { lifeScore: s } = computeScores(entry);
              return (
                <div key={entry.date} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full rounded-sm transition-all duration-500"
                    style={{
                      height: `${Math.max(4, (s / 100) * 40)}px`,
                      background: s >= 70 ? "#10b981" : s >= 45 ? "#f59e0b" : "#ef4444",
                      opacity: 0.8,
                    }}
                    title={`${entry.date}: ${s}`}
                  />
                  <span className="text-[9px] text-muted-foreground">{entry.date.slice(5)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Input Pillars */}
      {/* ── Health ── */}
      <Card className="gloss-panel rounded-2xl overflow-hidden">
        <button
          className="w-full flex items-center justify-between p-4 hover:bg-muted/20 transition-colors"
          onClick={() => setExpandedPillar(expandedPillar === "Health" ? null : "Health")}
        >
          <div className="flex items-center gap-2">
            <Flame className="w-5 h-5 text-emerald-400" />
            <span className="font-semibold">Health</span>
            <span className="text-sm text-muted-foreground">— {breakdown.Health}/100</span>
          </div>
          {expandedPillar === "Health" ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {expandedPillar === "Health" && (
          <div className="px-4 pb-4 space-y-3 border-t border-border/40 pt-3">
            <InputRow icon={Moon} label="Sleep hours" value={today.sleepHours} min={0} max={12} step={0.5} unit="h" onChange={u("sleepHours")} isSlider />
            <InputRow icon={Moon} label="Sleep quality" value={today.sleepQuality} min={1} max={5} unit="/5" onChange={u("sleepQuality")} />
            <InputRow icon={Dumbbell} label="Exercise" value={today.exerciseMinutes} min={0} max={180} step={5} unit="min" onChange={u("exerciseMinutes")} isSlider />
            <InputRow icon={Droplets} label="Water glasses" value={today.waterGlasses} min={0} max={12} onChange={u("waterGlasses")} />
            <InputRow icon={Smile} label="Healthy meals" value={today.mealsHealthy} min={0} max={3} onChange={u("mealsHealthy")} />
          </div>
        )}
      </Card>

      {/* ── Productivity ── */}
      <Card className="gloss-panel rounded-2xl overflow-hidden">
        <button
          className="w-full flex items-center justify-between p-4 hover:bg-muted/20 transition-colors"
          onClick={() => setExpandedPillar(expandedPillar === "Productivity" ? null : "Productivity")}
        >
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-indigo-400" />
            <span className="font-semibold">Productivity</span>
            <span className="text-sm text-muted-foreground">— {breakdown.Productivity}/100</span>
          </div>
          {expandedPillar === "Productivity" ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {expandedPillar === "Productivity" && (
          <div className="px-4 pb-4 space-y-3 border-t border-border/40 pt-3">
            <InputRow icon={Clock} label="Study time" value={today.studyMinutes} min={0} max={480} step={15} unit="min" onChange={u("studyMinutes")} isSlider />
            <InputRow icon={CheckSquare} label="Tasks done" value={today.tasksCompleted} min={0} max={20} onChange={u("tasksCompleted")} />
            <InputRow icon={Brain} label="Deep work blocks" value={today.deepWorkBlocks} min={0} max={8} onChange={u("deepWorkBlocks")} />
          </div>
        )}
      </Card>

      {/* ── Digital Wellbeing ── */}
      <Card className="gloss-panel rounded-2xl overflow-hidden">
        <button
          className="w-full flex items-center justify-between p-4 hover:bg-muted/20 transition-colors"
          onClick={() => setExpandedPillar(expandedPillar === "Digital Wellbeing" ? null : "Digital Wellbeing")}
        >
          <div className="flex items-center gap-2">
            <Monitor className="w-5 h-5 text-amber-400" />
            <span className="font-semibold">Digital Wellbeing</span>
            <span className="text-sm text-muted-foreground">— {breakdown["Digital Wellbeing"]}/100</span>
          </div>
          {expandedPillar === "Digital Wellbeing" ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {expandedPillar === "Digital Wellbeing" && (
          <div className="px-4 pb-4 space-y-3 border-t border-border/40 pt-3">
            <InputRow icon={Monitor} label="Screen time" value={today.screenTimeHours} min={0} max={16} step={0.5} unit="h" onChange={u("screenTimeHours")} isSlider />
            <InputRow icon={Monitor} label="Social media" value={today.socialMediaMinutes} min={0} max={240} step={5} unit="min" onChange={u("socialMediaMinutes")} isSlider />
            <InputRow icon={TreePine} label="Outdoors" value={today.outdoorMinutes} min={0} max={180} step={5} unit="min" onChange={u("outdoorMinutes")} isSlider />
          </div>
        )}
      </Card>

      {/* ── Mental ── */}
      <Card className="gloss-panel rounded-2xl overflow-hidden">
        <button
          className="w-full flex items-center justify-between p-4 hover:bg-muted/20 transition-colors"
          onClick={() => setExpandedPillar(expandedPillar === "Mental" ? null : "Mental")}
        >
          <div className="flex items-center gap-2">
            <Smile className="w-5 h-5 text-pink-400" />
            <span className="font-semibold">Mental & Mindfulness</span>
            <span className="text-sm text-muted-foreground">— {breakdown.Mental}/100</span>
          </div>
          {expandedPillar === "Mental" ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {expandedPillar === "Mental" && (
          <div className="px-4 pb-4 space-y-3 border-t border-border/40 pt-3">
            <InputRow icon={Smile} label="Mood" value={today.moodScore} min={1} max={5} unit="/5" onChange={u("moodScore")} />
            <InputRow icon={Smile} label="Stress level" value={today.stressLevel} min={1} max={5} unit="/5" onChange={u("stressLevel")} />
            <InputRow icon={Brain} label="Meditation" value={today.meditationMinutes} min={0} max={60} step={5} unit="min" onChange={u("meditationMinutes")} isSlider />
          </div>
        )}
      </Card>
    </div>
  );
}
