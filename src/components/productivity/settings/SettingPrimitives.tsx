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

export function WeaponCallout() {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-muted-foreground space-y-2">
      <p className="font-medium text-foreground text-xs uppercase tracking-wider">Two weapons</p>
      <div className="grid gap-2 sm:grid-cols-2 text-[12px]">
        <div className="rounded-lg border border-sky-400/20 bg-sky-500/5 p-3">
          <p className="font-semibold text-sky-100">SoftLand</p>
          <p className="mt-1 text-muted-foreground leading-snug">
            Blocks <strong className="text-foreground/85">websites</strong> in Edge (Gate). Does not kill Steam.
          </p>
        </div>
        <div className="rounded-lg border border-rose-400/20 bg-rose-500/5 p-3">
          <p className="font-semibold text-rose-100">Arm</p>
          <p className="mt-1 text-muted-foreground leading-snug">
            Kills listed <strong className="text-foreground/85">apps</strong> at the OS. Does not SoftLand URLs.
          </p>
        </div>
      </div>
      <p className="text-[11px] text-muted-foreground">
        SoftLand ON is never Armed. Turning SoftLand on does not arm anything.
      </p>
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
      <div className="flex flex-wrap items-start justify-between gap-2 px-1">
        <div className="min-w-0 space-y-1">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h2>
          <p className="text-[12px] text-muted-foreground leading-snug max-w-2xl">{why}</p>
        </div>
        {availability ? <NativeOrApiBadge kind={availability} /> : null}
      </div>
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 sm:p-6 space-y-4">{children}</div>
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
