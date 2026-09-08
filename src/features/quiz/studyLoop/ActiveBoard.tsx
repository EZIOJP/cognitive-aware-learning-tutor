import { useState, type DragEvent, type ReactNode } from "react";
import { Archive, ArrowRight, GripVertical } from "lucide-react";
import { Button } from "../../../app/components/ui/button";
import type { StudyLoopTag } from "../../../api/globalQuizClient";
import {
  filterTagsByKind,
  KIND_FILTERS,
  kindCount,
  tagBoardKind,
  type KindFilter,
} from "./dailyLearnKinds";
import { ACTIVE_TAG_CAP } from "./activeTagsStorage";

type DropZone = "active" | "backlog";

type Props = {
  active: StudyLoopTag[];
  backlog: StudyLoopTag[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onActivate: (id: string) => void;
  onPark: (id: string) => void;
  activeKind: KindFilter;
  backlogKind: KindFilter;
  onActiveKind: (k: KindFilter) => void;
  onBacklogKind: (k: KindFilter) => void;
  capHint: boolean;
};

export function ActiveBoard({
  active,
  backlog,
  selectedId,
  onSelect,
  onActivate,
  onPark,
  activeKind,
  backlogKind,
  onActiveKind,
  onBacklogKind,
  capHint,
}: Props) {
  const [dragId, setDragId] = useState<string | null>(null);
  const [overZone, setOverZone] = useState<DropZone | null>(null);

  const activeVisible = filterTagsByKind(active, activeKind);
  const backlogVisible = filterTagsByKind(backlog, backlogKind);

  const moveTo = (id: string, dest: DropZone) => {
    if (dest === "active") onActivate(id);
    else onPark(id);
  };

  const onZoneDragOver = (zone: DropZone) => (e: DragEvent) => {
    e.preventDefault();
    setOverZone(zone);
  };

  const onZoneDrop = (zone: DropZone) => (e: DragEvent) => {
    e.preventDefault();
    const id = e.dataTransfer.getData("text/tag-id") || dragId;
    if (id) moveTo(id, zone);
    setDragId(null);
    setOverZone(null);
  };

  return (
    <div className="space-y-3">
      {capHint ? (
        <p className="text-xs text-amber-800 dark:text-amber-200 bg-amber-500/10 border border-amber-500/30 rounded-md px-3 py-2">
          Active set is full (max {ACTIVE_TAG_CAP}). Park a topic first.
        </p>
      ) : null}

      <div className="grid lg:grid-cols-2 gap-4">
        <Column
          title="Currently Active Topics"
          hint={`Heavy focus · soft cap ${ACTIVE_TAG_CAP}`}
          hot={overZone === "active"}
          kind={activeKind}
          onKind={onActiveKind}
          counts={KIND_FILTERS.map((k) => ({ ...k, count: kindCount(active, k.id) }))}
          onDragOver={onZoneDragOver("active")}
          onDragLeave={() => setOverZone(null)}
          onDrop={onZoneDrop("active")}
        >
          {activeVisible.length === 0 ? (
            <p className="text-xs text-muted-foreground py-6 text-center">
              Drag from Backlog or tap Activate.
            </p>
          ) : (
            <ul className="space-y-2">
              {activeVisible.map((tag) => (
                <TopicCard
                  key={String(tag.id)}
                  tag={tag}
                  selected={selectedId === String(tag.id)}
                  zone="active"
                  onSelect={() => onSelect(String(tag.id))}
                  onPark={() => onPark(String(tag.id))}
                  onDragStart={(id) => setDragId(id)}
                  onDragEnd={() => {
                    setDragId(null);
                    setOverZone(null);
                  }}
                />
              ))}
            </ul>
          )}
        </Column>

        <Column
          title="Backlog"
          hint="Parked topics — activate when a slot frees"
          hot={overZone === "backlog"}
          kind={backlogKind}
          onKind={onBacklogKind}
          counts={KIND_FILTERS.map((k) => ({ ...k, count: kindCount(backlog, k.id) }))}
          onDragOver={onZoneDragOver("backlog")}
          onDragLeave={() => setOverZone(null)}
          onDrop={onZoneDrop("backlog")}
        >
          {backlogVisible.length === 0 ? (
            <p className="text-xs text-muted-foreground py-6 text-center">
              No backlog tags for this filter.
            </p>
          ) : (
            <ul className="space-y-2 max-h-[28rem] overflow-y-auto pr-1">
              {backlogVisible.slice(0, 80).map((tag) => (
                <TopicCard
                  key={String(tag.id)}
                  tag={tag}
                  selected={selectedId === String(tag.id)}
                  zone="backlog"
                  onSelect={() => onSelect(String(tag.id))}
                  onActivate={() => onActivate(String(tag.id))}
                  onDragStart={(id) => setDragId(id)}
                  onDragEnd={() => {
                    setDragId(null);
                    setOverZone(null);
                  }}
                />
              ))}
            </ul>
          )}
        </Column>
      </div>
    </div>
  );
}

function Column({
  title,
  hint,
  hot,
  kind,
  onKind,
  counts,
  children,
  onDragOver,
  onDragLeave,
  onDrop,
}: {
  title: string;
  hint: string;
  hot: boolean;
  kind: KindFilter;
  onKind: (k: KindFilter) => void;
  counts: { id: KindFilter; label: string; count: number }[];
  children: ReactNode;
  onDragOver: (e: DragEvent) => void;
  onDragLeave: () => void;
  onDrop: (e: DragEvent) => void;
}) {
  return (
    <div
      className={`rounded-xl border p-3 space-y-3 transition ${
        hot ? "border-primary/60 bg-primary/5" : "border-border/50 bg-background/30"
      }`}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="text-[11px] text-muted-foreground mt-0.5">{hint}</p>
      </div>
      <div className="flex flex-wrap gap-1">
        {counts.map((k) => (
          <button
            key={k.id}
            type="button"
            onClick={() => onKind(k.id)}
            className={`px-2 py-0.5 rounded-md text-[11px] border transition ${
              kind === k.id
                ? "bg-primary/15 border-primary/40 text-primary font-medium"
                : "border-border/40 text-muted-foreground hover:text-foreground"
            }`}
          >
            {k.label} ({k.count})
          </button>
        ))}
      </div>
      {children}
    </div>
  );
}

function TopicCard({
  tag,
  selected,
  zone,
  onSelect,
  onPark,
  onActivate,
  onDragStart,
  onDragEnd,
}: {
  tag: StudyLoopTag;
  selected: boolean;
  zone: DropZone;
  onSelect: () => void;
  onPark?: () => void;
  onActivate?: () => void;
  onDragStart: (id: string) => void;
  onDragEnd: () => void;
}) {
  const id = String(tag.id || "");
  const label = String(tag.label || id);
  const kind = tagBoardKind(tag);
  const qCount = Number(tag.question_count || 0);
  const due = Number(tag.due_count || 0);

  return (
    <li>
      <div
        draggable
        onDragStart={(e) => {
          e.dataTransfer.setData("text/tag-id", id);
          e.dataTransfer.effectAllowed = "move";
          onDragStart(id);
        }}
        onDragEnd={onDragEnd}
        className={`rounded-lg border px-2.5 py-2 transition cursor-grab active:cursor-grabbing ${
          selected
            ? "border-primary/50 bg-primary/10"
            : "border-border/40 bg-background/50 hover:border-primary/30"
        }`}
      >
        <button type="button" className="w-full text-left" onClick={onSelect}>
          <div className="flex items-start gap-1.5">
            <GripVertical className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-1">
                <span className="text-sm font-medium truncate">{label}</span>
                <span className="text-[10px] uppercase text-muted-foreground">{kind}</span>
              </div>
              <p className="text-[10px] text-muted-foreground font-mono truncate">{id}</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                {qCount}Q{due > 0 ? ` · ${due} due` : ""}
                {tag.has_read_card ? " · read ✓" : ""}
              </p>
            </div>
          </div>
        </button>
        <div className="flex flex-wrap gap-1 mt-2 pl-5">
          {zone === "active" ? (
            onPark ? (
              <Button size="sm" variant="ghost" className="h-6 text-[10px] gap-0.5 ml-auto" onClick={onPark}>
                <Archive className="h-2.5 w-2.5" /> Park
              </Button>
            ) : null
          ) : onActivate ? (
            <Button size="sm" variant="outline" className="h-6 text-[10px] gap-0.5" onClick={onActivate}>
              <ArrowRight className="h-2.5 w-2.5" /> Activate
            </Button>
          ) : null}
        </div>
      </div>
    </li>
  );
}
