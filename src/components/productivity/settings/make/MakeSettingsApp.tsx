import { useState, type ReactNode } from "react";
import { WeaponCallout } from "../SettingPrimitives";
import FocusControlPanel from "../../FocusControlPanel";
import SoftLandSiteRulesPanel, { SOFTLAND_LADDER_ONE_LINER } from "../../SoftLandSiteRulesPanel";
import SoftLandModeFlagsPanel from "../../SoftLandModeFlagsPanel";
import GateSchedulesPanel from "../../GateSchedulesPanel";
import AppKillRulesPanel from "../../AppKillRulesPanel";
import ProductivityPolicyPanel from "../../ProductivityPolicyPanel";
import { DeviceBlockPanel } from "../../DeviceBlockPanel";
import { EnforcerWriteGate, useEnforcerReachability } from "../../EnforcerWriteGate";
import { FocusPerfReviewPanel } from "../../FocusPerfReviewPanel";
import { SidebarTitleStickerPanel } from "../SidebarTitleStickerPanel";
import { useFocusStatus } from "../../../../hooks/useFocusStatus";
import { isFocusDesktopShell } from "../../../../utils/focusDesktopShell";
import { cn } from "../../../../app/components/ui/utils";

/**
 * CT-like IA (pattern only — no CT code):
 * Overview → what’s on · Blocks → edit lists · Unlock → how free time works · Productive · More
 */
export type SettingsSectionId =
  | "overview"
  | "blocks"
  | "sites"
  | "apps"
  | "filters"
  | "unlock"
  | "productive"
  | "tools"
  | "more";

type BlockSubId = "sites" | "apps" | "filters";

const NAV: { id: SettingsSectionId; label: string; blurb: string }[] = [
  { id: "overview", label: "Overview", blurb: "What’s active now" },
  { id: "blocks", label: "Blocks", blurb: "Sites, apps, filters" },
  { id: "unlock", label: "Unlock", blurb: "Goal, pass, Arm" },
  { id: "productive", label: "Productive", blurb: "What counts" },
  { id: "more", label: "More", blurb: isFocusDesktopShell() ? "Look, export" : "Look, demo, export" },
];

const WRITE_SECTIONS: SettingsSectionId[] = [
  "blocks",
  "sites",
  "apps",
  "filters",
  "unlock",
  "productive",
];

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`gloss-panel rounded-xl border border-border/50 p-5 ${className}`}>
      {children}
    </div>
  );
}

function SectionHeader({
  title,
  description,
  badge,
}: {
  title: string;
  description?: string;
  badge?: ReactNode;
}) {
  return (
    <div className="mb-5">
      <div className="flex items-center gap-3 mb-1">
        <h2 className="text-[15px] font-semibold text-foreground tracking-tight">{title}</h2>
        {badge}
      </div>
      {description ? (
        <p className="text-[12px] text-muted-foreground leading-relaxed">{description}</p>
      ) : null}
    </div>
  );
}

function softlandModeLabel(softland: ReturnType<typeof useFocusStatus>["softland"]): string {
  if (!softland) return "—";
  if (!softland.softland_enabled) return "off";
  const rt = softland.runtime || {};
  const now = Date.now();
  const inc = rt.incubation_until ? Date.parse(String(rt.incubation_until)) : NaN;
  if (Number.isFinite(inc) && inc > now) return "study (incubation)";
  const free = rt.free_until ? Date.parse(String(rt.free_until)) : NaN;
  if (Number.isFinite(free) && free > now) return "free";
  return "study";
}

function LiveStatusStrip({ className = "" }: { className?: string }) {
  const snap = useFocusStatus();
  const reach = useEnforcerReachability();
  const softlandOn = snap.softland?.softland_enabled;
  const armed = snap.enforcerStatus?.armed;
  const mode = softlandModeLabel(snap.softland);
  const productiveMin =
    snap.dayRollup?.productive_minutes != null
      ? Math.floor(snap.dayRollup.productive_minutes)
      : snap.dayRollup?.productive_seconds != null
        ? Math.floor(snap.dayRollup.productive_seconds / 60)
        : null;
  const goalMin =
    typeof snap.softland?.goals?.daily_focus_minutes === "number"
      ? Math.floor(Number(snap.softland.goals.daily_focus_minutes))
      : snap.dayRollup?.daily_focus_minutes != null
        ? Math.floor(snap.dayRollup.daily_focus_minutes)
        : null;

  const enfLabel =
    reach === "ok"
      ? "enforcer up"
      : reach === "down"
        ? "enforcer down"
        : reach === "no_bridge"
          ? "no bridge"
          : "enforcer…";

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-border/40 bg-[#1C1B19] px-3 py-2 text-[11px] font-mono text-[#E8E6DF]",
        className,
      )}
      aria-label="Site block and Arm status"
    >
      <span className={softlandOn ? "text-[#7DCFC4]" : "text-[#BDB9AE]"}>
        Site block {softlandOn == null ? "—" : softlandOn ? "ON" : "OFF"}
      </span>
      <span className="text-[#BDB9AE]">mode: {mode}</span>
      <span className={armed ? "text-[#E8A07A]" : "text-[#BDB9AE]"}>
        Arm: {armed == null ? "—" : armed ? "armed" : "disarmed"}
      </span>
      <span
        className={
          reach === "ok"
            ? "text-[#9FCB8A]"
            : reach === "down" || reach === "no_bridge"
              ? "text-[#E8A07A]"
              : "text-[#BDB9AE]"
        }
      >
        {enfLabel}
      </span>
      {productiveMin != null ? (
        <span className="ml-auto text-[#E8E6DF]">
          Today {productiveMin}
          {goalMin != null ? ` / ${goalMin}` : ""} min
        </span>
      ) : null}
    </div>
  );
}

function OverviewSection({ onJump }: { onJump: (id: SettingsSectionId) => void }) {
  return (
    <div className="space-y-5">
      {!isFocusDesktopShell() ? <LiveStatusStrip /> : null}
      <WeaponCallout onEditSites={() => onJump("sites")} onEditArm={() => onJump("unlock")} />
      <Card className="space-y-2 text-[13px] text-muted-foreground leading-relaxed">
        <p className="text-foreground font-semibold text-[15px]">Day flow</p>
        <ol className="list-decimal pl-5 space-y-1.5">
          <li>Tick a Bible chapter. Until then sites show the morning gate.</li>
          <li>Confirm the plan. Site block turns on, Arm turns on.</li>
          <li>Reach your daily goal. Sites open for the rest of the day.</li>
        </ol>
      </Card>
    </div>
  );
}

function BlocksSection({
  sub,
  onSubChange,
  onPolicySaved,
}: {
  sub: BlockSubId;
  onSubChange: (id: BlockSubId) => void;
  onPolicySaved?: () => void;
}) {
  const tabs: { id: BlockSubId; label: string; note: string }[] = [
    { id: "sites", label: "Sites", note: "browser" },
    { id: "apps", label: "Apps", note: "OS kill list" },
    { id: "filters", label: "Filters", note: "hosts file" },
  ];

  return (
    <div className="space-y-5">
      <div
        className="flex flex-wrap gap-4 border-b border-border/40"
        role="tablist"
        aria-label="Block type"
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={sub === t.id}
            onClick={() => onSubChange(t.id)}
            className={cn(
              "min-h-11 px-1 pb-2 text-[15px] transition-colors -mb-px",
              sub === t.id
                ? "border-b-[3px] border-[#0B6B63] font-semibold text-[#0B4F49]"
                : "border-b-[3px] border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}{" "}
            <span className="text-[12px] font-normal opacity-70">{t.note}</span>
          </button>
        ))}
      </div>

      {sub === "sites" && (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <div className="space-y-5">
            <Card>
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <h3 className="text-[15px] font-semibold">Site block</h3>
                  <p className="text-[13px] text-muted-foreground mt-1">
                    Master switch for websites only. Off allows every site.
                  </p>
                </div>
              </div>
              <ProductivityPolicyPanel variant="softland" onSaved={onPolicySaved} />
            </Card>
            <Card>
              <h3 className="text-[15px] font-semibold mb-1">Site rules</h3>
              <p className="text-[13px] text-muted-foreground mb-3">
                {SOFTLAND_LADDER_ONE_LINER} Click a domain to remove it.
              </p>
              <SoftLandSiteRulesPanel />
            </Card>
          </div>
          <div className="space-y-5">
            <Card>
              <h3 className="text-[15px] font-semibold mb-1">What each mode blocks</h3>
              <p className="text-[13px] text-muted-foreground mb-3">
                Social, keywords, other and strict allowlist did nothing in the code, so they are not
                shown.
              </p>
              <SoftLandModeFlagsPanel />
            </Card>
            <Card>
              <h3 className="text-[15px] font-semibold mb-1">Schedule</h3>
              <p className="text-[13px] text-muted-foreground mb-3">
                First matching window wins. Incubation overrides both and puts you back in study.
              </p>
              <GateSchedulesPanel />
            </Card>
          </div>
        </div>
      )}

      {sub === "apps" && (
        <Card>
          <h3 className="text-[15px] font-semibold mb-1">Kill list</h3>
          <p className="text-[13px] text-muted-foreground mb-3">
            Armed means any of these apps is closed on sight. Website domains never go here. Click an
            app to remove it.
          </p>
          <AppKillRulesPanel />
        </Card>
      )}

      {sub === "filters" && (
        <Card>
          <h3 className="text-[15px] font-semibold mb-1">Device lock (hosts file)</h3>
          <p className="text-[13px] text-muted-foreground mb-3">
            Blocks porn domains for every app on this PC. Site rules cannot override it. Needs admin
            to apply.
          </p>
          <DeviceBlockPanel />
        </Card>
      )}
    </div>
  );
}

function UnlockSection({ onPolicySaved }: { onPolicySaved?: () => void }) {
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <Card>
        <h3 className="text-[15px] font-semibold mb-1">Daily goal</h3>
        <p className="text-[13px] text-muted-foreground mb-3">
          Earn free time by hitting the goal after Bible + Confirm — or skip with a reward day / pass.
        </p>
        <ProductivityPolicyPanel variant="unlock" onSaved={onPolicySaved} />
      </Card>
      <Card>
        <h3 className="text-[15px] font-semibold mb-1">Arm</h3>
        <p className="text-[13px] text-muted-foreground mb-3">
          Own switch from Site block. Edit the kill list under Blocks → Apps.
        </p>
        <FocusControlPanel />
      </Card>
    </div>
  );
}

function ProductiveSection({
  onPolicySaved,
  productiveExtra,
}: {
  onPolicySaved?: () => void;
  productiveExtra?: ReactNode;
}) {
  return (
    <div className="space-y-6">
      <SectionHeader
        title="Productive"
        description="What minutes count toward the unlock clock — categories and thresholds, not site rules."
      />
      <Card>
        <ProductivityPolicyPanel variant="scoring" onSaved={onPolicySaved} />
      </Card>
      {productiveExtra}
    </div>
  );
}

type MakeSettingsAppProps = {
  section?: SettingsSectionId;
  onSectionChange?: (id: SettingsSectionId) => void;
  onPolicySaved?: () => void;
  productiveExtra?: ReactNode;
  toolsContent?: ReactNode;
};

function navHighlight(section: SettingsSectionId): SettingsSectionId {
  if (section === "sites" || section === "apps" || section === "filters" || section === "blocks")
    return "blocks";
  if (section === "tools" || section === "more") return "more";
  return section;
}

function blockSubFromSection(section: SettingsSectionId): BlockSubId {
  if (section === "apps" || section === "filters") return section;
  return "sites";
}

export default function MakeSettingsApp({
  section: sectionProp,
  onSectionChange,
  onPolicySaved,
  productiveExtra,
  toolsContent,
}: MakeSettingsAppProps) {
  const [sectionLocal, setSectionLocal] = useState<SettingsSectionId>("overview");
  const section = sectionProp ?? sectionLocal;
  const setSection = (id: SettingsSectionId) => {
    if (onSectionChange) onSectionChange(id);
    else setSectionLocal(id);
  };

  const highlight = navHighlight(section);
  const blockSub = blockSubFromSection(section);

  const body =
    highlight === "overview" ? (
      <OverviewSection onJump={setSection} />
    ) : highlight === "blocks" ? (
      <BlocksSection
        sub={blockSub}
        onSubChange={(id) => setSection(id)}
        onPolicySaved={onPolicySaved}
      />
    ) : highlight === "unlock" ? (
      <UnlockSection onPolicySaved={onPolicySaved} />
    ) : highlight === "productive" ? (
      <ProductiveSection onPolicySaved={onPolicySaved} productiveExtra={productiveExtra} />
    ) : (
      <div>
        <SectionHeader
          title="More"
          description="Preferences and tools that aren’t block lists — look, demo clock, watch sync, export, setup."
        />
        <div className="mb-6 gloss-panel rounded-xl border border-border/50 p-5">
          <SidebarTitleStickerPanel />
        </div>
        <div className="mb-6">
          <FocusPerfReviewPanel />
        </div>
        {toolsContent}
      </div>
    );

  return (
    <div className="flex flex-col min-h-[70vh] h-full bg-background text-foreground overflow-hidden">
      <header className="flex-shrink-0 border-b border-border/50 bg-card/30 px-4 pt-4 pb-3 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-2 mb-3">
          <div>
            <h1 className="text-[15px] font-semibold text-foreground tracking-tight">Settings</h1>
            <p className="text-[12px] text-muted-foreground mt-0.5">
              Site block and Arm are separate switches. Turning one on never turns on the other.
            </p>
          </div>
        </div>
        {isFocusDesktopShell() ? <LiveStatusStrip className="mb-3" /> : null}
        <nav className="flex flex-wrap gap-2" aria-label="Settings sections">
          {NAV.map(({ id, label, blurb }) => (
            <button
              key={id}
              type="button"
              title={blurb}
              onClick={() => setSection(id === "blocks" ? "sites" : id === "more" ? "tools" : id)}
              className={cn(
                "min-h-11 rounded-full px-4 text-[14px] font-medium border transition-colors",
                highlight === id
                  ? "border-[#1C1B19] bg-[#1C1B19] text-white"
                  : "border-[#D6D3CA] bg-background text-foreground hover:bg-accent/40",
              )}
            >
              {label}
            </button>
          ))}
        </nav>
      </header>

      <main className="flex-1 overflow-y-auto p-5 sm:p-6">
        {WRITE_SECTIONS.includes(section) || highlight === "blocks" ? (
          <EnforcerWriteGate>{body}</EnforcerWriteGate>
        ) : (
          body
        )}
      </main>
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
  if (id === "sites" || id === "apps" || id === "filters" || id === "tools") {
    return id as SettingsSectionId;
  }
  // Legacy hub / Make rail ids
  if (id === "now" || id === "focus" || id === "enforcer") return "unlock";
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
