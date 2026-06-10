import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { Brain, BarChart3, PenLine, Route } from "lucide-react";
import { DashboardWidgetGrid } from "../components/dashboard/DashboardWidgetGrid";
import type { DashboardWidget } from "../components/dashboard/dashboardWidgetUtils";
import { CheckpointRoadmap, type CheckpointItem } from "../components/roadmap/CheckpointRoadmap";
import { MATH_TOPICS } from "../features/math/data/topics";
import { useAuth } from "../context/AuthContext";
import { authFetch } from "../features/vocab/api/authClient";
import { Badge } from "../app/components/ui/badge";
import { Card } from "../app/components/ui/card";

interface MasteryTopic {
  topic: string;
  mastery_points: number;
  status: string;
}

/** Drill types aligned with reference Simplify Quiz UI */
const DRILL_TYPES = [
  { id: "algebra", label: "Algebra / Simplify", topic: "Algebra" },
  { id: "calculus", label: "Calculus / Derivatives", topic: "Calculus" },
  { id: "geometry", label: "Geometry / Angles", topic: "Geometry" },
  { id: "trigonometry", label: "Trigonometry", topic: "Trigonometry" },
];

export function MathDashboardPage() {
  const { token } = useAuth();
  const [mastery, setMastery] = useState<MasteryTopic[]>([]);

  useEffect(() => {
    if (!token) return;
    authFetch("/math/mastery", token)
      .then((r) => setMastery((r.data as { topics?: MasteryTopic[] }).topics || []))
      .catch(() => setMastery([]));
  }, [token]);

  const roadmapItems: CheckpointItem[] = useMemo(() => {
    const byTopic = new Map(mastery.map((m) => [m.topic, m]));
    return MATH_TOPICS.map((t, i) => {
      const m = byTopic.get(t.backendTopic);
      const progress = m?.mastery_points ?? 0;
      const prev = MATH_TOPICS[i - 1];
      const prevM = prev ? byTopic.get(prev.backendTopic) : null;
      const prevDone = !prev || (prevM?.mastery_points ?? 0) >= 40;
      let status: CheckpointItem["status"] = "available";
      if (progress >= 80) status = "complete";
      else if (progress > 0 || i === 0) status = "current";
      else if (!prevDone) status = "locked";
      return {
        id: t.id,
        label: t.label,
        subtitle: `${t.questionCount} drills`,
        progress,
        status,
        href: status !== "locked" ? `/math-tutor/topic/${t.id}` : undefined,
      };
    });
  }, [mastery]);

  const avgMastery = mastery.length
    ? Math.round(mastery.reduce((s, m) => s + m.mastery_points, 0) / mastery.length)
    : 0;

  const widgets: DashboardWidget[] = useMemo(
    () => [
      {
        id: "math-drills",
        title: "Start a drill",
        icon: PenLine,
        accent: "from-violet-500/25 to-indigo-500/10",
        defaultColSpan: 2,
        component: (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground mb-2">Select a drill — 5 questions + whiteboard</p>
            {DRILL_TYPES.map((drill) => (
              <Link
                key={drill.id}
                to={`/math-tutor/practice/${drill.id}`}
                className="block rounded-xl border p-3 hover:border-primary/50 hover:bg-accent/20 transition-colors"
              >
                <span className="font-medium text-sm">{drill.label}</span>
                <span className="block text-xs text-muted-foreground mt-0.5">
                  {drill.topic} · 5 questions
                </span>
              </Link>
            ))}
          </div>
        ),
      },
      {
        id: "math-checkpoints",
        title: "Topic checkpoints",
        icon: Route,
        accent: "from-emerald-500/15 to-teal-500/10",
        defaultColSpan: 2,
        component: (
          <CheckpointRoadmap layout="horizontal" compact items={roadmapItems} />
        ),
      },
      {
        id: "math-intro",
        title: "Math Relearn Curve",
        icon: Brain,
        accent: "from-blue-500/15 to-cyan-500/10",
        component: (
          <div className="space-y-2">
            <Badge variant="secondary">Topic roadmap</Badge>
            <p className="text-sm text-muted-foreground">
              Read formulas, practice with the split whiteboard, then review reports.
            </p>
            {token ? (
              <p className="text-xs text-muted-foreground">Overall mastery: {avgMastery}/100</p>
            ) : (
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Log in to save mastery and session reports.
              </p>
            )}
          </div>
        ),
      },
      {
        id: "math-links",
        title: "Quick links",
        icon: BarChart3,
        accent: "from-amber-500/15 to-orange-500/10",
        component: (
          <div className="space-y-2 text-sm">
            <Link to="/math-tutor/reports" className="block text-primary hover:underline">
              View all session reports →
            </Link>
            <Link to="/math-tutor/recognize-test" className="block text-primary hover:underline">
              Handwriting recognition test →
            </Link>
            <Link to="/math-tutor/train" className="block text-primary hover:underline">
              Train my OCR (handwriting curriculum) →
            </Link>
            <Link to="/study-room" className="block text-primary hover:underline">
              Study Room (tldraw + OCR) →
            </Link>
            <p className="text-xs text-muted-foreground">
              Arithmetic & Algebra use the live API when logged in. Geometry, Calculus, and Trig use local drill sets.
            </p>
          </div>
        ),
      },
    ],
    [roadmapItems, token, avgMastery]
  );

  return (
    <div className="h-full min-h-0 flex flex-col">
      <Card className="gloss-panel mx-1 mb-4 p-4 shrink-0 border-primary/20">
        <h2 className="text-lg font-semibold mb-1">Math Relearn Curve</h2>
        <p className="text-sm text-muted-foreground">
          Pick a drill below or follow topic checkpoints — same flow as the reference quiz UI.
        </p>
      </Card>
      <div className="flex-1 min-h-0">
        <DashboardWidgetGrid
          storageKey="math-dash"
          title="Practice & progress"
          subtitle="Customize widgets with Edit widgets"
          widgets={widgets}
        />
      </div>
    </div>
  );
}
