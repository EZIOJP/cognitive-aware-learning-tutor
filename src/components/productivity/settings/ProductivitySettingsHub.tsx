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

/** Prefer MakeSettingsApp in Focus; hub kept for Study interstitial / deep links. */
export type SettingsSectionId =
  | "overview"
  | "blocks"
  | "now"
  | "sites"
  | "apps"
  | "unlock"
  | "productive"
  | "filters"
  | "tools"
  | "more";

const NAV: { id: SettingsSectionId; label: string; blurb: string }[] = [
  { id: "overview", label: "Overview", blurb: "What’s active" },
  { id: "blocks", label: "Blocks", blurb: "Sites, apps, filters" },
  { id: "unlock", label: "Unlock", blurb: "Goal, pass, Arm" },
  { id: "productive", label: "Productive", blurb: "What counts" },
  { id: "more", label: "More", blurb: "Demo, export" },
];

export type ProductivitySettingsHubProps = {
  section: SettingsSectionId;
  onSectionChange: (id: SettingsSectionId) => void;
  onPolicySaved?: () => void;
  productiveExtra?: ReactNode;
  toolsContent?: ReactNode;
};

function navHighlight(section: SettingsSectionId): SettingsSectionId {
  if (section === "sites" || section === "apps" || section === "filters" || section === "blocks")
    return "blocks";
  if (section === "now") return "unlock";
  if (section === "tools" || section === "more") return "more";
  return section;
}

export function ProductivitySettingsHub({
  section,
  onSectionChange,
  onPolicySaved,
  productiveExtra,
  toolsContent,
}: ProductivitySettingsHubProps) {
  const highlight = navHighlight(section);
  const blockSub =
    section === "apps" || section === "filters" ? section : ("sites" as const);

  const gatedBody = (
    <>
      {highlight === "overview" && (
        <div className="space-y-4">
          <WeaponCallout />
          <div className="rounded-2xl border border-border/40 bg-muted/15 p-4 sm:p-5 space-y-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Jump
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {(
                [
                  ["blocks", "Blocks — sites, apps, device filter"],
                  ["unlock", "Unlock — goal, pass, Arm"],
                  ["productive", "Productive — scoring"],
                  ["more", "More — demo, export"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() =>
                    onSectionChange(id === "blocks" ? "sites" : id === "more" ? "tools" : id)
                  }
                  className="rounded-xl border border-border/40 bg-background/35 px-3 py-2.5 text-left text-[12px] text-foreground/90 hover:border-sky-400/30 hover:bg-sky-500/5"
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <NativeOrApiBadge kind="native" />
              <span className="text-[11px] text-muted-foreground self-center">
                SoftLand = sites · Arm = kills · SoftLand ON ≠ Armed
              </span>
            </div>
          </div>
        </div>
      )}

      {highlight === "blocks" && (
        <div className="space-y-6">
          <div className="flex flex-wrap gap-1 rounded-xl border border-border/40 bg-muted/15 p-1">
            {(
              [
                ["sites", "Sites"],
                ["apps", "Apps"],
                ["filters", "Filters"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => onSectionChange(id)}
                className={`rounded-lg px-3 py-1.5 text-[12px] ${
                  blockSub === id ? "bg-foreground/10 text-foreground" : "text-muted-foreground"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {blockSub === "sites" && (
            <>
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
                why="First matching week window sets study/free mode."
                availability="native"
              >
                <GateSchedulesPanel />
              </SettingSection>
            </>
          )}
          {blockSub === "apps" && (
            <SettingSection
              title="Apps (Arm)"
              why="OS process kills only. SoftLand site lists never belong here."
              availability="native"
            >
              <AppKillRulesPanel />
            </SettingSection>
          )}
          {blockSub === "filters" && (
            <SettingSection
              title="Filters"
              why="Permanent PC-wide porn block via Windows hosts."
              availability="native"
            >
              <DeviceBlockPanel />
            </SettingSection>
          )}
        </div>
      )}

      {highlight === "unlock" && (
        <div className="space-y-6">
          <SettingSection
            title="Unlock"
            why="Earn goal+Bible, reward day, or day pass. SoftLand ON ≠ Armed."
            availability="native"
          >
            <ProductivityPolicyPanel variant="unlock" onSaved={onPolicySaved} />
          </SettingSection>
          <SettingSection
            title="Now"
            why="Live SoftLand mode and OS Arm."
            availability="native"
          >
            <FocusControlPanel />
          </SettingSection>
        </div>
      )}

      {highlight === "productive" && (
        <div className="space-y-6">
          <SettingSection
            title="What counts as productive"
            why="Threshold and categories feed the unlock clock."
            availability="api"
          >
            <ProductivityPolicyPanel variant="scoring" onSaved={onPolicySaved} />
          </SettingSection>
          {productiveExtra}
        </div>
      )}

      {highlight === "more" && (
        <SettingSection title="More" why="Demo clock, watch sync, reminders, export, install docs.">
          <DesktopManagedBanner feature="Watch sync and some tools" />
          {toolsContent}
        </SettingSection>
      )}
    </>
  );

  return (
    <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:gap-6">
      <nav
        aria-label="Settings groups"
        className="lg:sticky lg:top-20 lg:w-52 shrink-0 space-y-0.5 rounded-2xl border border-border/40 bg-muted/15 p-1.5"
      >
        {NAV.map((item) => {
          const active = highlight === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() =>
                onSectionChange(
                  item.id === "blocks" ? "sites" : item.id === "more" ? "tools" : item.id,
                )
              }
              className={`w-full rounded-xl px-3 py-2 text-left transition-colors ${
                active
                  ? "bg-foreground/10 text-foreground"
                  : "text-muted-foreground hover:bg-background/40 hover:text-foreground"
              }`}
            >
              <div className="text-[13px] font-medium">{item.label}</div>
              <div className="text-[10px] opacity-70">{item.blurb}</div>
            </button>
          );
        })}
      </nav>
      <div className="min-w-0 flex-1">
        {highlight === "overview" || highlight === "more" ? (
          gatedBody
        ) : (
          <EnforcerWriteGate>{gatedBody}</EnforcerWriteGate>
        )}
      </div>
    </div>
  );
}

export function parseSettingsSection(raw: string | null): SettingsSectionId {
  const id = (raw || "overview").toLowerCase();
  if (NAV.some((n) => n.id === id)) {
    if (id === "blocks") return "sites";
    if (id === "more") return "tools";
    return id as SettingsSectionId;
  }
  if (id === "sites" || id === "apps" || id === "filters" || id === "tools" || id === "now") {
    return id as SettingsSectionId;
  }
  if (id === "focus" || id === "enforcer") return "unlock";
  if (id === "rules" || id === "policy" || id === "schedules") return "sites";
  if (id === "scoring" || id === "classification") return "productive";
  if (
    id === "watch" ||
    id === "demo" ||
    id === "demo-mode" ||
    id === "export" ||
    id === "setup" ||
    id === "reminders" ||
    id === "planning"
  ) {
    return "tools";
  }
  return "overview";
}
