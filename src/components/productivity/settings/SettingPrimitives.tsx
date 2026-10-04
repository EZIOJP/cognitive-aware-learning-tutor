import type { ReactNode } from "react";

export type Availability = "native" | "api";

export function NativeOrApiBadge({ kind }: { kind: Availability }) {
  if (kind === "native") {
    return (
      <span className="inline-flex items-center rounded-full border border-emerald-400/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-emerald-100/90">
        Works offline
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-100/90">
      Needs API
    </span>
  );
}

export function WeaponCallout({
  onEditSites,
  onEditArm,
}: {
  onEditSites?: () => void;
  onEditArm?: () => void;
} = {}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 text-[12px]">
      <div className="rounded-xl border border-border/50 bg-background/40 p-4 space-y-3">
        <div>
          <h3 className="text-[15px] font-semibold text-foreground tracking-tight">Site block</h3>
          <p className="mt-1.5 text-muted-foreground leading-relaxed">
            Blocks websites in the browser. It knows about study, free and incubation, and an unlisted
            site is allowed. A wrong verdict fixes itself on the next page load.
          </p>
        </div>
        {onEditSites ? (
          <button
            type="button"
            onClick={onEditSites}
            className="min-h-11 rounded-lg border border-border/60 bg-background px-4 text-[13px] font-medium text-foreground hover:bg-accent/50"
          >
            Edit site rules
          </button>
        ) : null}
      </div>
      <div className="rounded-xl border border-border/50 bg-background/40 p-4 space-y-3">
        <div>
          <h3 className="text-[15px] font-semibold text-foreground tracking-tight">Arm</h3>
          <p className="mt-1.5 text-muted-foreground leading-relaxed">
            Kills apps at the OS level. It only checks armed and the kill list, and it ignores mode. A
            wrong kill is destructive, so it is its own switch.
          </p>
        </div>
        {onEditArm ? (
          <button
            type="button"
            onClick={onEditArm}
            className="min-h-11 rounded-lg border border-border/60 bg-background px-4 text-[13px] font-medium text-foreground hover:bg-accent/50"
          >
            Arm controls
          </button>
        ) : null}
      </div>
    </div>
  );
}

type SectionProps = {
  title: string;
  why: string;
  availability?: Availability;
  children: ReactNode;
  className?: string;
};

export function SettingSection({ title, why, availability, children, className = "" }: SectionProps) {
  return (
    <section className={`space-y-3 ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-2 px-0.5">
        <div className="min-w-0 space-y-1">
          <h2 className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            {title}
          </h2>
          <p className="text-[12px] text-muted-foreground leading-snug max-w-2xl">{why}</p>
        </div>
        {availability ? <NativeOrApiBadge kind={availability} /> : null}
      </div>
      <div className="gloss-panel rounded-2xl border border-border/40 p-4 sm:p-5 space-y-4">
        {children}
      </div>
    </section>
  );
}

type RowProps = {
  label: string;
  consequence: string;
  control: ReactNode;
};

export function SettingRow({ label, consequence, control }: RowProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-white/5 bg-black/20 px-3 py-2.5">
      <div className="min-w-0 flex-1 space-y-0.5">
        <p className="text-xs font-medium text-foreground/90">{label}</p>
        <p className="text-[11px] text-muted-foreground leading-snug">{consequence}</p>
      </div>
      <div className="shrink-0">{control}</div>
    </div>
  );
}
