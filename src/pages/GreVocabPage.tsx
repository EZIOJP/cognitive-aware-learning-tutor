import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import {
  BookOpen,
  Layers,
  Clock,
  AlertTriangle,
  FileJson,
  Database,
  Map,
  Route,
} from "lucide-react";
import { Card } from "../app/components/ui/card";
import { Badge } from "../app/components/ui/badge";
import { DashboardWidgetGrid } from "../components/dashboard/DashboardWidgetGrid";
import type { DashboardWidget } from "../components/dashboard/dashboardWidgetUtils";
import { CheckpointRoadmap, type CheckpointItem } from "../components/roadmap/CheckpointRoadmap";
import { getGroupsDetailed } from "../features/vocab/cycle/cycleService";
import type { GroupSummary } from "../features/vocab/cycle/types";

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

export function GreVocabPage() {
  const [groups, setGroups] = useState<GroupSummary[]>([]);

  useEffect(() => {
    getGroupsDetailed().then(setGroups).catch(() => setGroups([]));
  }, []);

  const roadmapItems = useMemo(
    () => groups.map((g, i) => groupToCheckpoint(g, i, groups)),
    [groups]
  );

  const widgets: DashboardWidget[] = useMemo(
    () => [
      {
        id: "vocab-intro",
        title: "GRE Vocabulary",
        icon: Database,
        accent: "from-emerald-500/20 to-green-500/10",
        defaultColSpan: 2,
        component: (
          <div className="space-y-2">
            <Badge variant="secondary" className="text-[10px]">
              30 words / group
            </Badge>
            <p className="text-sm text-muted-foreground">
              Follow the group checkpoint roadmap, then use Read or Cycle for each batch of 30 words.
            </p>
          </div>
        ),
      },
      {
        id: "vocab-checkpoints",
        title: "Group checkpoints",
        icon: Route,
        accent: "from-teal-500/15 to-emerald-500/10",
        defaultColSpan: 2,
        component:
          roadmapItems.length > 0 ? (
            <CheckpointRoadmap layout="horizontal" compact items={roadmapItems} />
          ) : (
            <p className="text-sm text-muted-foreground">Loading groups…</p>
          ),
      },
      {
        id: "vocab-modules",
        title: "Study modules",
        icon: Map,
        accent: "from-blue-500/15 to-indigo-500/10",
        defaultColSpan: 2,
        defaultRowSpan: 2,
        component: (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {VOCAB_MODULES.map(({ key, name, icon: Icon, status, to, description }) => (
              <Card key={key} className="p-3 flex flex-col border bg-background/40">
                <div className="flex items-start justify-between mb-2">
                  <Icon className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                  <Badge variant={status === "live" ? "default" : "secondary"} className="text-[10px]">
                    {status === "live" ? "Ready" : "Planned"}
                  </Badge>
                </div>
                <h4 className="font-medium text-sm mb-1">{name}</h4>
                <p className="text-xs text-muted-foreground mb-2 flex-1">{description}</p>
                {to ? (
                  <Link to={to} className="text-xs font-medium text-primary hover:underline">
                    Open →
                  </Link>
                ) : null}
              </Card>
            ))}
          </div>
        ),
      },
    ],
    [roadmapItems]
  );

  return (
    <DashboardWidgetGrid
      storageKey="vocab-dash"
      title="GRE Vocabulary"
      subtitle="Group checkpoints and study modules"
      widgets={widgets}
    />
  );
}
