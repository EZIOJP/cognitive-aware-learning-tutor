import type { ReactNode } from "react";
import {
  LayoutDashboard,
  Radio,
  Globe2,
  AppWindow,
  Unlock,
  Gauge,
  Filter,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { WeaponCallout, SettingSection, NativeOrApiBadge } from "./SettingPrimitives";
import FocusControlPanel from "../FocusControlPanel";
import SoftLandSiteRulesPanel from "../SoftLandSiteRulesPanel";
import GateSchedulesPanel from "../GateSchedulesPanel";
import AppKillRulesPanel from "../AppKillRulesPanel";
import ProductivityPolicyPanel from "../ProductivityPolicyPanel";
import { DeviceBlockPanel } from "../DeviceBlockPanel";
import { DesktopManagedBanner } from "../DesktopManagedBanner";

export type SettingsSectionId =
  | "overview"
  | "now"
  | "sites"
  | "apps"
  | "unlock"
  | "productive"
  | "filters"
  | "tools";

const NAV: { id: SettingsSectionId; label: string; blurb: string; Icon: LucideIcon }[] = [
  { id: "overview", label: "Overview", blurb: "How it works", Icon: LayoutDashboard },
  { id: "now", label: "Now", blurb: "Mode · earn · Arm", Icon: Radio },
  { id: "sites", label: "Sites", blurb: "Lists · schedule", Icon: Globe2 },
  { id: "apps", label: "Apps", blurb: "Kill list · Arm", Icon: AppWindow },
  { id: "unlock", label: "Unlock", blurb: "Goal · pass · reward", Icon: Unlock },
  { id: "productive", label: "Productive", blurb: "Scores", Icon: Gauge },
  { id: "filters", label: "Filters", blurb: "Hosts block", Icon: Filter },
  { id: "tools", label: "Tools", blurb: "Demo · watch", Icon: Wrench },
];

export type ProductivitySettingsHubProps = {
  section: SettingsSectionId;
  onSectionChange: (id: SettingsSectionId) => void;
  onPolicySaved?: () => void;
  productiveExtra?: ReactNode;
  toolsContent?: ReactNode;
};

export function ProductivitySettingsHub({
  section,
  onSectionChange,
  onPolicySaved,
  productiveExtra,
  toolsContent,
}: ProductivitySettingsHubProps) {
  return (
    <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:gap-8">
      <nav
        aria-label="Settings groups"
        className="lg:sticky lg:top-20 lg:w-[13.5rem] shrink-0 rounded-2xl border border-white/[0.07] bg-zinc-950/50 p-1.5 backdrop-blur-sm"
      >
        <p className="px-2.5 pt-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-500">
          Settings
        </p>
        <div className="space-y-0.5">
          {NAV.map((item) => {
            const active = section === item.id;
            const Icon = item.Icon;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSectionChange(item.id)}
                className={`group flex w-full items-start gap-2.5 rounded-xl px-2.5 py-2 text-left transition-colors ${
                  active
                    ? "bg-white/[0.09] text-zinc-50 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]"
                    : "text-zinc-500 hover:bg-white/[0.04] hover:text-zinc-300"
                }`}
              >
                <span
                  className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border ${
                    active
                      ? "border-teal-500/30 bg-teal-500/10 text-teal-200"
                      : "border-white/[0.06] bg-black/20 text-zinc-500 group-hover:text-zinc-400"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" aria-hidden />
                </span>
                <span className="min-w-0 pt-0.5">
                  <span className="block text-[12px] font-semibold tracking-tight">{item.label}</span>
                  <span className="block text-[10px] opacity-75 mt-0.5 leading-snug">{item.blurb}</span>
                </span>
              </button>
            );
          })}
        </div>
      </nav>

      <div className="min-w-0 flex-1 space-y-6">
        {section === "overview" && (
          <div className="space-y-5">
            <WeaponCallout />
            <div className="rounded-2xl border border-white/[0.07] bg-zinc-950/40 p-5 space-y-4">
              <div>
                <p className="text-[13px] font-semibold tracking-tight text-zinc-100">Start here</p>
                <p className="mt-1 text-[12px] text-zinc-500">
                  Each group is one job. Open one, finish it, leave — no mega-scroll.
                </p>
              </div>
              <div className="grid gap-2.5 sm:grid-cols-2">
                {(
                  [
                    ["sites", "Sites", "Allow / watch / block + week schedule"],
                    ["apps", "Apps", "OS kill list — Arm is under Now"],
                    ["unlock", "Unlock", "Daily goal, day pass, reward day"],
                    ["now", "Now", "Live mode, spend earned, Arm switch"],
                  ] as const
                ).map(([id, title, sub]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => onSectionChange(id)}
                    className="rounded-xl border border-white/[0.07] bg-black/30 px-3.5 py-3 text-left transition-colors hover:border-teal-500/25 hover:bg-teal-500/[0.05]"
                  >
                    <span className="block text-[12px] font-semibold text-zinc-100">{title}</span>
                    <span className="mt-0.5 block text-[11px] text-zinc-500 leading-snug">{sub}</span>
                  </button>
                ))}
              </div>
              <div className="flex flex-col gap-2 border-t border-white/[0.05] pt-3 sm:flex-row sm:flex-wrap sm:gap-x-6 sm:gap-y-2">
                <div className="flex items-center gap-2">
                  <NativeOrApiBadge kind="native" />
                  <span className="text-[11px] text-zinc-500">SoftLand · Arm · lists · schedules</span>
                </div>
                <div className="flex items-center gap-2">
                  <NativeOrApiBadge kind="api" />
                  <span className="text-[11px] text-zinc-500">Scores · hosts · watch sync</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {section === "now" && (
          <SettingSection
            title="Now"
            why="Live SoftLand mode and OS Arm. Edit site lists under Sites; full kill list under Apps."
            availability="native"
          >
            <FocusControlPanel />
          </SettingSection>
        )}

        {section === "sites" && (
          <div className="space-y-6">
            <SettingSection
              title="SoftLand master"
              why="Turns site blocking on or off. Does not Arm OS kills."
              availability="native"
            >
              <ProductivityPolicyPanel variant="softland" onSaved={onPolicySaved} />
            </SettingSection>
            <SettingSection
              title="Site lists"
              why="Allow always wins. Watch is study-only. Block survives reward days."
              availability="native"
            >
              <SoftLandSiteRulesPanel />
            </SettingSection>
            <SettingSection
              title="Schedule"
              why="First matching week window sets study/free mode. Use the day strip like a mini calendar."
              availability="native"
            >
              <GateSchedulesPanel />
            </SettingSection>
          </div>
        )}

        {section === "apps" && (
          <SettingSection
            title="Apps (Arm)"
            why="OS process kills only. SoftLand site lists never belong here."
            availability="native"
          >
            <AppKillRulesPanel />
            <p className="text-[11px] text-zinc-500 px-0.5">
              Arm / Disarm and lock mode live on{" "}
              <button
                type="button"
                className="text-teal-300/90 underline underline-offset-2 hover:text-teal-200"
                onClick={() => onSectionChange("now")}
              >
                Now
              </button>
              .
            </p>
          </SettingSection>
        )}

        {section === "unlock" && (
          <SettingSection
            title="Unlock"
            why="Three doors: earn goal + Bible chapter, spend a reward day, or use a day pass. Daily goal matches Plan’s daily focus."
            availability="api"
          >
            <p className="text-[11px] leading-relaxed text-amber-100/85 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-3.5 py-2.5">
              Until native unlock accounting (P5a), day-pass / reward claim need the API. A day pass may
              not open watch sites in SoftLand yet — prefer a reward day or free spend for browsing.
            </p>
            <ProductivityPolicyPanel variant="unlock" onSaved={onPolicySaved} />
          </SettingSection>
        )}

        {section === "productive" && (
          <div className="space-y-6">
            <SettingSection
              title="What counts as productive"
              why="Threshold and categories feed the unlock clock. Not SoftLand site rules."
              availability="api"
            >
              <ProductivityPolicyPanel variant="scoring" onSaved={onPolicySaved} />
            </SettingSection>
            {productiveExtra}
          </div>
        )}

        {section === "filters" && (
          <SettingSection
            title="PC-wide filters"
            why="Windows hosts file — all apps, needs admin. Separate from SoftLand’s porn heuristic."
            availability="api"
          >
            <DeviceBlockPanel />
          </SettingSection>
        )}

        {section === "tools" && (
          <SettingSection
            title="Tools"
            why="Demo clock, watch sync, reminders, export, and install docs."
          >
            <DesktopManagedBanner feature="Watch sync and some tools" />
            {toolsContent}
          </SettingSection>
        )}
      </div>
    </div>
  );
}

export function parseSettingsSection(raw: string | null): SettingsSectionId {
  const id = (raw || "overview").toLowerCase();
  if (NAV.some((n) => n.id === id)) return id as SettingsSectionId;
  if (id === "focus" || id === "enforcer") return "now";
  if (id === "policy" || id === "rules" || id === "schedules") return "sites";
  if (id === "scoring" || id === "classification") return "productive";
  if (
    id === "watch" ||
    id === "demo" ||
    id === "demo-mode" ||
    id === "export" ||
    id === "setup" ||
    id === "reminders" ||
    id === "planning"
  )
    return "tools";
  return "overview";
}
