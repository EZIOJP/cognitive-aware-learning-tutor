import { Link } from "react-router";
import { CheckCircle2, Circle, Lock } from "lucide-react";
import { cn } from "../../app/components/ui/utils";

export type CheckpointStatus = "complete" | "current" | "available" | "locked";

export interface CheckpointItem {
  id: string;
  label: string;
  subtitle?: string;
  progress: number;
  status: CheckpointStatus;
  href?: string;
}

interface CheckpointRoadmapProps {
  title?: string;
  description?: string;
  items: CheckpointItem[];
  className?: string;
  layout?: "vertical" | "horizontal";
  compact?: boolean;
}

function CheckpointNode({
  item,
  compact,
}: {
  item: CheckpointItem;
  compact?: boolean;
}) {
  const Icon =
    item.status === "complete"
      ? CheckCircle2
      : item.status === "locked"
        ? Lock
        : Circle;

  const body = (
    <div
      className={cn(
        "rounded-xl border bg-background/40 p-2 min-w-[100px] max-w-[140px] shrink-0 transition-colors",
        item.href && item.status !== "locked" && "hover:border-primary/50 hover:bg-accent/20",
        item.status === "current" && "border-primary ring-1 ring-primary/30",
        compact && "min-w-[88px] p-1.5"
      )}
    >
      <div className="flex items-center gap-1.5 mb-1">
        <Icon
          className={cn(
            "w-4 h-4 shrink-0",
            item.status === "complete" && "text-emerald-500",
            item.status === "current" && "text-primary",
            item.status === "locked" && "text-muted-foreground/40"
          )}
        />
        <span className={cn("font-medium truncate", compact ? "text-xs" : "text-sm")}>
          {item.label}
        </span>
      </div>
      {!compact && item.subtitle ? (
        <p className="text-[10px] text-muted-foreground line-clamp-2 mb-1">{item.subtitle}</p>
      ) : null}
      <div className="h-1 rounded-full bg-muted overflow-hidden">
        <div className="h-full bg-primary" style={{ width: `${Math.min(100, item.progress)}%` }} />
      </div>
      <p className="text-[10px] font-mono text-muted-foreground mt-0.5 text-right">
        {Math.round(item.progress)}%
      </p>
    </div>
  );

  if (item.href && item.status !== "locked") {
    return <Link to={item.href}>{body}</Link>;
  }
  return body;
}

export function CheckpointRoadmap({
  title,
  description,
  items,
  className,
  layout = "vertical",
  compact = false,
}: CheckpointRoadmapProps) {
  if (layout === "horizontal") {
    return (
      <div className={cn(className)}>
        {title ? <h3 className={cn("font-semibold mb-1", compact ? "text-sm" : "text-base")}>{title}</h3> : null}
        {description ? (
          <p className="text-xs text-muted-foreground mb-2">{description}</p>
        ) : null}
        <div className="overflow-x-auto pb-1 -mx-1 px-1">
          <div className="flex items-stretch gap-2 min-w-min">
            {items.map((item, i) => (
              <div key={item.id} className="flex items-center gap-2">
                <CheckpointNode item={item} compact={compact} />
                {i < items.length - 1 ? (
                  <div className="w-4 h-0.5 bg-border shrink-0 rounded" aria-hidden />
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("gloss-panel rounded-2xl p-5", className)}>
      {title ? <h3 className="text-lg font-semibold mb-1">{title}</h3> : null}
      {description ? (
        <p className="text-sm text-muted-foreground mb-4">{description}</p>
      ) : null}
      <div className="space-y-0">
        {items.map((item, i) => {
          const Icon =
            item.status === "complete"
              ? CheckCircle2
              : item.status === "locked"
                ? Lock
                : Circle;
          const row = (
            <div
              className={cn(
                "flex items-start gap-3 py-3",
                item.href && item.status !== "locked" && "hover:bg-accent/30 -mx-2 px-2 rounded-xl"
              )}
            >
              <div className="flex flex-col items-center shrink-0">
                <Icon
                  className={cn(
                    "w-5 h-5 mt-0.5",
                    item.status === "complete" && "text-emerald-500",
                    item.status === "current" && "text-primary fill-primary/20",
                    item.status === "locked" && "text-muted-foreground/50"
                  )}
                />
                {i < items.length - 1 ? (
                  <div className="w-0.5 flex-1 min-h-[24px] bg-border my-1" />
                ) : null}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex justify-between gap-2 items-baseline">
                  <span className="font-medium text-sm">{item.label}</span>
                  <span className="text-xs font-mono text-muted-foreground">
                    {Math.round(item.progress)}%
                  </span>
                </div>
                {item.subtitle ? (
                  <p className="text-xs text-muted-foreground mt-0.5">{item.subtitle}</p>
                ) : null}
                <div className="h-1.5 rounded-full bg-muted overflow-hidden mt-2">
                  <div
                    className="h-full bg-primary"
                    style={{ width: `${Math.min(100, item.progress)}%` }}
                  />
                </div>
              </div>
            </div>
          );
          if (item.href && item.status !== "locked") {
            return (
              <Link key={item.id} to={item.href} className="block">
                {row}
              </Link>
            );
          }
          return <div key={item.id}>{row}</div>;
        })}
      </div>
    </div>
  );
}
