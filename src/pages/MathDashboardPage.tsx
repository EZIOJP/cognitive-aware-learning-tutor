import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { Brain, BarChart3, PenLine, Route, CheckCircle2, Circle, Lock } from "lucide-react";
import type { CheckpointItem } from "../components/roadmap/CheckpointRoadmap";
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

function TopicCheckpointGrid({ items }: { items: CheckpointItem[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {items.map((item) => {
        const Icon =
          item.status === "complete"
            ? CheckCircle2
            : item.status === "locked"
              ? Lock
              : Circle;
        const statusLabel =
          item.status === "complete"
            ? "Complete"
            : item.status === "current"
              ? "Current"
              : item.status === "locked"
                ? "Locked"
                : "Ready";
        const card = (
          <div
            className={`flex min-h-[132px] flex-col rounded-2xl border p-4 transition-all duration-200 ${
              item.status === "current"
                ? "border-primary/70 bg-primary/15 shadow-[0_14px_35px_rgba(124,58,237,0.16)]"
                : item.status === "complete"
                  ? "border-primary/35 bg-primary/10"
                  : item.status === "locked"
                    ? "border-border/40 bg-muted/20 opacity-65"
                    : "border-border/50 bg-card/45 hover:border-primary/35 hover:bg-primary/5"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Topic</p>
                <h3 className="mt-1 text-sm font-semibold">{item.label}</h3>
              </div>
              <div className="grid h-8 w-8 place-items-center rounded-xl border border-border/40 bg-background/50">
                <Icon className={`h-4 w-4 ${item.status === "locked" ? "text-muted-foreground/50" : "text-primary"}`} />
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{item.subtitle}</p>
            <div className="mt-auto pt-3">
              <div className="mb-1 flex items-center justify-between gap-2 text-[10px]">
                <span className="text-muted-foreground">{statusLabel}</span>
                <span className="font-mono text-muted-foreground">{Math.round(item.progress)}%</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, item.progress)}%` }} />
              </div>
            </div>
          </div>
        );
        return item.href && item.status !== "locked" ? (
          <Link key={item.id} to={item.href} className="block hover:-translate-y-0.5 transition-transform">
            {card}
          </Link>
        ) : (
          <div key={item.id}>{card}</div>
        );
      })}
    </div>
  );
}

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

  return (
    <div className="h-full min-h-0 overflow-y-auto p-4 md:p-6">
      <div className="mx-auto max-w-6xl space-y-6">
        <section className="gloss-panel relative overflow-hidden rounded-3xl border border-primary/20 bg-gradient-to-br from-primary/10 via-card/80 to-accent/20 p-5">
          <div className="pointer-events-none absolute -right-16 -top-20 h-48 w-48 rounded-full bg-primary/15 blur-3xl" />
          <div className="relative flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-2xl border border-primary/20 bg-primary/10">
                <Brain className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-primary">Math tutor</p>
                <h1 className="text-2xl font-semibold">Math Relearn Curve</h1>
                <p className="text-sm text-muted-foreground">
                  Follow topic checkpoints, practice short drills, then review your session reports.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary" className="rounded-full border border-primary/20 bg-primary/10 text-primary">
                Mastery {avgMastery}/100
              </Badge>
              {!token ? (
                <Badge variant="secondary" className="rounded-full border border-amber-500/25 bg-amber-500/10 text-amber-300">
                  Start the API to save progress
                </Badge>
              ) : null}
            </div>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,24rem)]">
          <Card className="gloss-panel p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Route className="h-5 w-5 text-primary" />
                <div>
                  <h2 className="font-semibold">Topic checkpoints</h2>
                  <p className="text-xs text-muted-foreground">Move through fundamentals in order.</p>
                </div>
              </div>
              <Badge variant="secondary" className="rounded-full">
                {roadmapItems.length} topics
              </Badge>
            </div>
            <TopicCheckpointGrid items={roadmapItems} />
          </Card>

          <div className="space-y-6">
            <Card className="gloss-panel p-5 space-y-4">
              <div className="flex items-center gap-2">
                <PenLine className="h-5 w-5 text-primary" />
                <div>
                  <h2 className="font-semibold">Start a drill</h2>
                  <p className="text-xs text-muted-foreground">5 questions plus whiteboard.</p>
                </div>
              </div>
              <div className="space-y-2">
                {DRILL_TYPES.map((drill) => (
                  <Link
                    key={drill.id}
                    to={`/math-tutor/practice/${drill.id}`}
                    className="block rounded-2xl border border-border/50 bg-background/35 p-3 transition-colors hover:border-primary/50 hover:bg-primary/5"
                  >
                    <span className="font-medium text-sm">{drill.label}</span>
                    <span className="block text-xs text-muted-foreground mt-0.5">
                      {drill.topic} · 5 questions
                    </span>
                  </Link>
                ))}
              </div>
            </Card>

            <Card className="gloss-panel p-5 space-y-3">
              <div className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-primary" />
                <h2 className="font-semibold">Quick links</h2>
              </div>
              <div className="space-y-2 text-sm">
                <Link to="/math-tutor/reports" className="block text-primary hover:underline">
                  View all session reports →
                </Link>
                <Link to="/math-tutor/recognize-test" className="block text-primary hover:underline">
                  Handwriting recognition test →
                </Link>
                <Link to="/math-tutor/train" className="block text-primary hover:underline">
                  Train my OCR (collect samples) →
                </Link>
                <Link to="/math-tutor/training-data" className="block text-primary hover:underline">
                  OCR training data (edit / delete) →
                </Link>
                <Link to="/study-room" className="block text-primary hover:underline">
                  Study Room (tldraw + OCR) →
                </Link>
              </div>
              <p className="text-xs text-muted-foreground">
                Arithmetic and Algebra use the live API when logged in. Geometry, Calculus, and Trig use local drill sets.
              </p>
            </Card>
          </div>
        </section>
      </div>
    </div>
  );
}
