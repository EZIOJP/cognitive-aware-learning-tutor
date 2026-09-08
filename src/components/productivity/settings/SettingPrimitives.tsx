import type { ReactNode } from "react";
import { Globe2, Shield, ShieldOff } from "lucide-react";

export type Availability = "native" | "api";

export function NativeOrApiBadge({ kind }: { kind: Availability }) {
  if (kind === "native") {
    return (
      <span className="inline-flex items-center gap-1 rounded-md border border-teal-500/25 bg-teal-500/[0.08] px-2 py-0.5 text-[10px] font-medium tracking-wide text-teal-100/95">
        <span className="h-1.5 w-1.5 rounded-full bg-teal-400" aria-hidden />
        Offline OK
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-amber-500/25 bg-amber-500/[0.08] px-2 py-0.5 text-[10px] font-medium tracking-wide text-amber-100/95">
      <span className="h-1.5 w-1.5 rounded-full bg-amber-400" aria-hidden />
      Needs API
    </span>
  );
}

export function WeaponCallout() {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-gradient-to-br from-zinc-900/80 via-zinc-950/90 to-zinc-900/60 p-5 sm:p-6">
      <div
        className="pointer-events-none absolute -right-16 -top-20 h-48 w-48 rounded-full bg-teal-500/[0.07] blur-3xl"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute -bottom-24 -left-10 h-40 w-40 rounded-full bg-rose-500/[0.06] blur-3xl"
        aria-hidden
      />
      <p className="relative text-[11px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
        Two weapons
      </p>
      <p className="relative mt-1 max-w-xl text-sm text-zinc-300/90 leading-relaxed">
        SoftLand and Arm share your intent — nothing else. One blocks sites; one kills apps.
      </p>
      <div className="relative mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-teal-500/20 bg-teal-500/[0.06] p-4">
          <div className="flex items-center gap-2 text-teal-100">
            <Globe2 className="h-4 w-4 opacity-90" aria-hidden />
            <p className="text-sm font-semibold tracking-tight">SoftLand</p>
          </div>
          <p className="mt-2 text-[12px] leading-snug text-zinc-400">
            Blocks <span className="text-zinc-200">websites</span> in Edge (Gate). Never kills Steam.
          </p>
        </div>
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/[0.06] p-4">
          <div className="flex items-center gap-2 text-rose-100">
            <Shield className="h-4 w-4 opacity-90" aria-hidden />
            <p className="text-sm font-semibold tracking-tight">Arm</p>
          </div>
          <p className="mt-2 text-[12px] leading-snug text-zinc-400">
            Kills listed <span className="text-zinc-200">apps</span> at the OS. Never SoftLands URLs.
          </p>
        </div>
      </div>
      <p className="relative mt-4 flex items-start gap-2 text-[11px] text-zinc-500">
        <ShieldOff className="mt-0.5 h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden />
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
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-white/[0.06] pb-3 px-0.5">
        <div className="min-w-0 space-y-1">
          <h2 className="text-[13px] font-semibold tracking-tight text-zinc-100">{title}</h2>
          <p className="text-[12px] leading-relaxed text-zinc-500 max-w-2xl">{why}</p>
        </div>
        {availability ? <NativeOrApiBadge kind={availability} /> : null}
      </div>
      <div className="rounded-2xl border border-white/[0.07] bg-zinc-950/40 p-4 sm:p-5 space-y-4 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.04)]">
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
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-white/[0.05] bg-black/25 px-3.5 py-3">
      <div className="min-w-0 flex-1 space-y-0.5">
        <p className="text-[12px] font-medium text-zinc-100">{label}</p>
        <p className="text-[11px] leading-snug text-zinc-500">{consequence}</p>
      </div>
      <div className="shrink-0">{control}</div>
    </div>
  );
}
