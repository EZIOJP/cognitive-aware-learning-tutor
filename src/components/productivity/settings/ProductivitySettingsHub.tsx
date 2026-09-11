import type { ReactNode } from "react";
import { WeaponCallout, SettingSection, NativeOrApiBadge } from "./SettingPrimitives";
import FocusControlPanel from "../FocusControlPanel";
import SoftLandSiteRulesPanel from "../SoftLandSiteRulesPanel";
import GateSchedulesPanel from "../GateSchedulesPanel";
import AppKillRulesPanel from "../AppKillRulesPanel";
import ProductivityPolicyPanel from "../ProductivityPolicyPanel";
import { DeviceBlockPanel } from "../DeviceBlockPanel";
import { DesktopManagedBanner } from "../DesktopManagedBanner";
import { EnforcerWriteGate } from "../EnforcerWriteGate";

export type SettingsSectionId =
  | "overview"
  | "now"
  | "sites"
  | "apps"
  | "unlock"
  | "productive"
  | "filters"
  | "tools";

const NAV: { id: SettingsSectionId; label: string; blurb: string }[] = [
  { id: "overview", label: "Overview", blurb: "How blocking works" },
  { id: "now", label: "Now", blurb: "Mode, earn, Arm" },
  { id: "sites", label: "Sites", blurb: "SoftLand lists & schedule" },
  { id: "apps", label: "Apps", blurb: "Kill list & Arm" },
  { id: "unlock", label: "Unlock", blurb: "Goal, pass, reward" },
  { id: "productive", label: "Productive", blurb: "Scores & categories" },
  { id: "filters", label: "Filters", blurb: "Hosts porn block" },
  { id: "tools", label: "Tools", blurb: "Demo, watch, export" },
];

export type ProductivitySettingsHubProps = {
  section: SettingsSectionId;
  onSectionChange: (id: SettingsSectionId) => void;
  onPolicySaved?: () => void;
  /** Scoring / session tools that need page timeline state */
  productiveExtra?: ReactNode;
  /** Demo, watch, reminders, export, setup — owned by the page */
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
    <EnforcerWriteGate>
    <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
      <nav
        aria-label="Settings groups"
        className="lg:sticky lg:top-20 lg:w-52 shrink-0 space-y-1 rounded-2xl border border-white/10 bg-white/[0.03] p-2"
      >
        {NAV.map((item) => {
          const active = section === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSectionChange(item.id)}
              className={`w-full rounded-xl px-3 py-2 text-left transition-colors ${
                active
                  ? "bg-white/10 text-foreground"
                  : "text-muted-foreground hover:bg-white/5 hover:text-foreground/90"
              }`}
            >
              <span className="block text-xs font-semibold">{item.label}</span>
              <span className="block text-[10px] opacity-80 mt-0.5">{item.blurb}</span>
            </button>
          );
        })}
      </nav>

      <div className="min-w-0 flex-1 space-y-6">
        {section === "overview" && (
          <div className="space-y-4">
            <WeaponCallout />
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 sm:p-6 space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Jump to a group
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {(
                  [
                    ["sites", "Sites — allow / watch / block + week schedule"],
                    ["apps", "Apps — OS kill list and Arm"],
                    ["unlock", "Unlock — daily goal, day pass, reward day"],
                    ["now", "Now — live mode, spend earned, Arm switch"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => onSectionChange(id)}
                    className="rounded-xl border border-white/10 bg-black/20 px-3 py-2.5 text-left text-[12px] text-foreground/90 hover:border-sky-400/30 hover:bg-sky-500/5"
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap gap-2 pt-1">
                <NativeOrApiBadge kind="native" />
                <span className="text-[11px] text-muted-foreground self-center">
                  SoftLand, Arm, lists, schedules — work with API down
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                <NativeOrApiBadge kind="api" />
                <span className="text-[11px] text-muted-foreground self-center">
                  Scores, hosts filter, watch sync — need :8000
                </span>
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
            why="OS process kills only. SoftLand site lists never belong here. Arm from Now or below."
            availability="native"
          >
            <AppKillRulesPanel />
            <p className="text-[11px] text-muted-foreground px-1">
              Arm / Disarm and lock mode live on{" "}
              <button
                type="button"
                className="underline text-sky-300/90"
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
            why="Three doors: earn goal+Bible chapter, spend a reward day, or use a day pass. Daily goal is the same number as Plan’s daily focus."
            availability="api"
          >
            <p className="text-[11px] text-amber-200/80 rounded-lg border border-amber-400/20 bg-amber-500/5 px-3 py-2">
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
    </EnforcerWriteGate>
  );
}

export function parseSettingsSection(raw: string | null): SettingsSectionId {
  const id = (raw || "overview").toLowerCase();
  if (NAV.some((n) => n.id === id)) return id as SettingsSectionId;
  // Legacy hashes / anchors
  if (id === "focus" || id === "enforcer") return "now";
  if (id === "policy" || id === "rules" || id === "schedules") return "sites";
  if (id === "scoring" || id === "classification") return "productive";
  if (id === "watch" || id === "demo" || id === "demo-mode" || id === "export" || id === "setup" || id === "reminders" || id === "planning")
    return "tools";
  return "overview";
}
