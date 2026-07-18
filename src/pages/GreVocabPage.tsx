import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import {
  BookOpen,
  Layers,
  Clock,
  AlertTriangle,
  FileJson,
  Map,
  Route,
  Play,
  Loader2,
  RefreshCw,
  Shield,
  CheckCircle2,
  Lock,
  Circle,
} from "lucide-react";
import { Card } from "../app/components/ui/card";
import { Button } from "../app/components/ui/button";
import { Badge } from "../app/components/ui/badge";
import type { CheckpointItem } from "../components/roadmap/CheckpointRoadmap";
import { getGroupsDetailed } from "../features/vocab/cycle/cycleService";
import type { GroupSummary } from "../features/vocab/cycle/types";
import { useAuth } from "../context/AuthContext";

const VOCAB_MODULES = [
  {
    key: "read",
    name: "Read Mode",
    icon: BookOpen,
    status: "live" as const,
    to: "/gre-vocab/read",
    description: "Browse all words with search, groups, and keyboard nav",
  },
  {
    key: "read-low",
    name: "Low Mastery",
    icon: AlertTriangle,
    status: "live" as const,
    to: "/gre-vocab/read/low-mastery",
    description: "Mastery 0 or below",
  },
  {
    key: "read-due",
    name: "Due Reviews",
    icon: Clock,
    status: "live" as const,
    to: "/gre-vocab/read/due",
    description: "Spaced repetition queue",
  },
  {
    key: "add-words",
    name: "Add Words (JSON)",
    icon: FileJson,
    status: "live" as const,
    to: "/gre-vocab/add-words",
    description: "Paste JSON — preview, validate, import (admin)",
  },
  {
    key: "cycle",
    name: "Cycle Manager",
    icon: Layers,
    status: "live" as const,
    to: "/gre-vocab/cycle",
    description: "Read → Quiz → Report per group, with low-mastery loops",
  },
];

function groupToCheckpoint(g: GroupSummary, i: number, groups: GroupSummary[]): CheckpointItem {
  const progress = g.total_words > 0 ? (g.words_mastered / g.total_words) * 100 : 0;
  const prev = groups[i - 1];
  const prevOk = !prev || prev.is_completed || prev.words_started >= prev.total_words * 0.5;
  let status: CheckpointItem["status"] = "available";
  if (g.is_completed || progress >= 90) status = "complete";
  else if (g.words_started > 0 || i === 0) status = "current";
  else if (!prevOk) status = "locked";
  return {
    id: String(g.group_number),
    label: `G${g.group_number}`,
    subtitle: `${g.words_mastered}/${g.total_words}`,
    progress,
    status,
    href: status !== "locked" ? "/gre-vocab/cycle" : undefined,
  };
}

function CheckpointHero({
  loading,
  groups,
  roadmapItems,
}: {
  loading: boolean;
  groups: GroupSummary[];
  roadmapItems: CheckpointItem[];
}) {
  const current = roadmapItems.find((item) => item.status === "current") ?? roadmapItems.find((item) => item.status !== "locked");
  const currentIndex = Math.max(
    0,
    roadmapItems.findIndex((item) => item.id === current?.id)
  );
  const timelineStart = Math.max(0, currentIndex - 1);
  const visibleRoadmapItems = roadmapItems.slice(timelineStart, timelineStart + 6);
  const hiddenBefore = timelineStart;
  const hiddenAfter = Math.max(0, roadmapItems.length - timelineStart - visibleRoadmapItems.length);

  return (
    <div className="rounded-2xl border border-border/50 bg-background/35 p-3 space-y-3 shadow-inner">
      {loading ? (
        <p className="text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" />
          Loading groups…
        </p>
      ) : groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No word groups yet. Ensure the API is running, or import words in Admin.
        </p>
      ) : (
        <>
          <div className="rounded-2xl border border-primary/20 bg-gradient-to-r from-primary/10 via-primary/5 to-transparent p-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-wider text-primary/75">Current checkpoint</p>
                <h3 className="mt-1 text-lg font-semibold">{current?.label ?? "No active group"}</h3>
                <p className="text-xs text-muted-foreground">
                  {current?.subtitle ?? "Start the first 30-word group"} words mastered
                </p>
              </div>
              <div className="min-w-[10rem] flex-1 sm:max-w-xs">
                <div className="mb-1 flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>Checkpoint progress</span>
                  <span className="font-mono text-primary">{Math.round(current?.progress ?? 0)}%</span>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, current?.progress ?? 0)}%` }} />
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-border/40 bg-card/35 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h4 className="text-sm font-semibold">Next checkpoints</h4>
                <p className="text-xs text-muted-foreground">
                  Focus on the next few groups. Locked groups open as the earlier group progresses.
                </p>
              </div>
              <span className="rounded-full border border-border/50 bg-background/50 px-2.5 py-1 text-[11px] text-muted-foreground">
                G{timelineStart + 1}-G{timelineStart + visibleRoadmapItems.length} of {roadmapItems.length}
                {hiddenBefore > 0 ? ` · ${hiddenBefore} earlier` : ""}
                {hiddenAfter > 0 ? ` · ${hiddenAfter} later` : ""}
              </span>
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                {visibleRoadmapItems.map((item) => {
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
                  const node = (
                    <div
                      className={`flex min-h-[108px] flex-col rounded-2xl border p-3 transition-all duration-200 ${
                        item.status === "current"
                          ? "border-primary/70 bg-primary/15 shadow-[0_14px_35px_rgba(124,58,237,0.18)]"
                          : item.status === "complete"
                            ? "border-primary/35 bg-primary/10"
                            : item.status === "locked"
                              ? "border-border/40 bg-muted/20 opacity-60"
                              : "border-border/50 bg-background/45 hover:border-primary/35 hover:bg-primary/5"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Group</p>
                          <h5 className="text-base font-semibold">{item.label}</h5>
                        </div>
                        <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-border/40 bg-background/50">
                          <Icon className={`h-4 w-4 ${item.status === "locked" ? "text-muted-foreground/50" : "text-primary"}`} />
                        </div>
                      </div>

                      <div className="mt-3 flex items-center justify-between gap-2">
                        <span className="text-xs text-muted-foreground">{item.subtitle} words</span>
                        <span className="rounded-full bg-background/60 px-2 py-0.5 text-[10px] text-muted-foreground">
                          {statusLabel}
                        </span>
                      </div>
                      <div className="mt-auto pt-3">
                        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                          <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, item.progress)}%` }} />
                        </div>
                        <p className="mt-1 text-right text-[10px] font-mono text-muted-foreground">
                          {Math.round(item.progress)}%
                        </p>
                      </div>
                    </div>
                  );
                  return item.href && item.status !== "locked" ? (
                    <Link key={item.id} to={item.href} className="block hover:-translate-y-0.5 transition-transform">
                      {node}
                    </Link>
                  ) : (
                    <div key={item.id}>{node}</div>
                  );
                })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function StudyModulesSection() {
  return (
    <section className="mx-1 space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl border border-primary/20 bg-primary/10 flex items-center justify-center">
            <Map className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">Study modules</h2>
            <p className="text-xs text-muted-foreground">
              Choose the exact GRE workflow you want to open next.
            </p>
          </div>
        </div>
        <Badge variant="secondary" className="rounded-full border border-primary/20 bg-primary/10 text-primary">
          {VOCAB_MODULES.length} ready
        </Badge>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {VOCAB_MODULES.map(({ key, name, icon: Icon, status, to, description }) => (
          <Link key={key} to={to} className="group block min-h-[145px]">
            <Card className="relative h-full overflow-hidden rounded-2xl border border-border/50 bg-card/50 p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:bg-primary/5 hover:shadow-[0_18px_45px_rgba(15,23,42,0.25)]">
              <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
              <div className="flex h-full flex-col">
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" />
                  </div>
                  <Badge
                    variant="secondary"
                    className="rounded-full border border-primary/20 bg-primary/10 text-[10px] text-primary"
                  >
                    {status === "live" ? "Ready" : "Planned"}
                  </Badge>
                </div>

                <div className="flex flex-1 flex-col">
                  <h3 className="text-base font-semibold">{name}</h3>
                  <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">{description}</p>
                  <span className="mt-3 inline-flex items-center text-sm font-medium text-primary">
                    Open
                    <span className="ml-1 transition-transform group-hover:translate-x-1">→</span>
                  </span>
                </div>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  );
}

export function GreVocabPage() {
  const { isAuthenticated, isAdmin } = useAuth();
  const [groups, setGroups] = useState<GroupSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const g = await getGroupsDetailed();
      setGroups(g);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load vocabulary data");
      setGroups([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload, isAuthenticated]);

  const roadmapItems = useMemo(
    () => groups.map((g, i) => groupToCheckpoint(g, i, groups)),
    [groups]
  );
  const checkpointProgress = useMemo(() => {
    const completed = roadmapItems.filter((item) => item.status === "complete").length;
    const available = roadmapItems.filter((item) => item.status !== "locked").length;
    const total = roadmapItems.length;
    const overall = total > 0 ? Math.round((completed / total) * 100) : 0;
    return { available, completed, overall, total };
  }, [roadmapItems]);

  return (
    <div className="space-y-4">
      <section className="gloss-panel relative mx-1 overflow-hidden rounded-3xl border border-primary/20 bg-gradient-to-br from-primary/10 via-card/80 to-accent/30 p-4 space-y-4">
        <div className="pointer-events-none absolute -right-16 -top-20 h-48 w-48 rounded-full bg-primary/15 blur-3xl" />
        <div className="pointer-events-none absolute -left-20 bottom-0 h-40 w-40 rounded-full bg-accent/30 blur-3xl" />

        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-2xl border border-primary/20 bg-primary/10 flex items-center justify-center shadow-sm">
              <Route className="w-4 h-4 text-primary" />
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-primary">GRE roadmap</p>
              <h2 className="text-lg font-semibold">Pick up from your next checkpoint</h2>
              <p className="text-sm text-muted-foreground">
                A calm 30-word path: read, quiz, review, then unlock the next group.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1.5 text-xs text-primary">
              <span className="font-semibold tabular-nums">{checkpointProgress.overall}%</span>
              <span className="ml-1 text-primary/70">
                total · {checkpointProgress.completed}/{checkpointProgress.total} complete · {checkpointProgress.available} unlocked
              </span>
            </div>
            <Button
              asChild
              size="sm"
              className="shrink-0"
              disabled={!!error && groups.length === 0}
            >
              <Link to="/gre-vocab/cycle">
                <Play className="w-3.5 h-3.5 mr-1" />
                Continue cycle
              </Link>
            </Button>
          </div>
        </div>

        <div className="relative">
          <CheckpointHero loading={loading} groups={groups} roadmapItems={roadmapItems} />
        </div>
      </section>

      {error ? (
        <div className="mx-1 px-4 py-3 rounded-xl border border-destructive/40 bg-destructive/10 text-sm flex flex-wrap items-center justify-between gap-2">
          <span>{error}</span>
          <Button type="button" size="sm" variant="outline" onClick={() => void reload()}>
            <RefreshCw className="w-3.5 h-3.5 mr-1" />
            Retry
          </Button>
        </div>
      ) : null}

      {isAdmin ? (
        <div className="mx-1 px-4 py-2 rounded-xl border border-border/50 flex items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2 text-muted-foreground">
            <Shield className="w-4 h-4" />
            Admin: import words, reset users, export groups
          </span>
          <Link to="/admin" className="font-medium text-primary hover:underline">
            Open Admin Panel →
          </Link>
        </div>
      ) : null}

      <StudyModulesSection />
    </div>
  );
}
