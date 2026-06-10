import { cn } from "../../app/components/ui/utils";

interface HeroProgressProps {
  value: number;
  label?: string;
  className?: string;
}

export function HeroProgress({ value, label, className }: HeroProgressProps) {
  const pct = Math.min(100, Math.max(0, value));

  return (
    <div className={cn("space-y-2", className)}>
      {label ? (
        <div className="flex items-center justify-between gap-2">
          <span className="hero-label text-muted-foreground">{label}</span>
          <span className="hero-label text-primary">{pct}%</span>
        </div>
      ) : null}
      <div className="hero-progress-track rounded-sm">
        <div
          className="hero-progress-fill"
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    </div>
  );
}
