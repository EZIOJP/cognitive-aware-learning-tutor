import { useState, type ReactNode } from "react";
import {
  CircleUserRound,
  Database,
  LayoutDashboard,
  Palette,
  Settings2,
  Shield,
  SunMedium,
  Unlock,
  type LucideIcon,
} from "lucide-react";
import { WeaponCallout } from "../SettingPrimitives";
import ProductivityPolicyPanel from "../../ProductivityPolicyPanel";
import { DeviceBlockPanel } from "../../DeviceBlockPanel";
import { BlocksBoardPanel } from "../../BlocksBoardPanel";
import { EnforcerWriteGate, useEnforcerReachability } from "../../EnforcerWriteGate";
import { FocusPerfReviewPanel } from "../../FocusPerfReviewPanel";
import { FocusAiStatusChip } from "../../FocusAiStatusChip";
import { UnlockGuidePanel } from "../../UnlockGuidePanel";
import { ArmControlCard } from "../../ArmControlCard";
import { SidebarTitleStickerPanel } from "../SidebarTitleStickerPanel";
import { ThemeSettingsPanel } from "../ThemeSettingsPanel";
import { useFocusStatus } from "../../../../hooks/useFocusStatus";
import { isFocusDesktopShell } from "../../../../utils/focusDesktopShell";
import { cn } from "../../../../app/components/ui/utils";

/**
 * Production Settings IA (system-design jobs + ui-ux-pro-max chrome):
 * Overview · Blocks · Unlock · Day · Appearance · Profile · Data · Advanced
 * SoftLand ≠ Arm. Legacy ids (more/tools/productive/…) still parse.
 */
export type SettingsSectionId =
  | "overview"
  | "blocks"
  | "sites"
  | "apps"
  | "limits"
  | "filters"
  | "review"
  | "unlock"
  | "day"
  | "appearance"
  | "profile"
  | "data"
  | "advanced"
  /** @deprecated → day */
  | "productive"
  /** @deprecated → day */
  | "tools"
  /** @deprecated → day */
  | "more";

type BlockSubId = "board" | "review";
type NavId =
  | "overview"
  | "blocks"
  | "unlock"
  | "day"
  | "appearance"
  | "profile"
  | "data"
  | "advanced";

const NAV: { id: NavId; label: string; blurb: string; Icon: LucideIcon }[] = [
  { id: "overview", label: "Overview", blurb: "What’s on right now", Icon: LayoutDashboard },
  { id: "blocks", label: "Blocks", blurb: "Board + classify", Icon: Shield },
  { id: "unlock", label: "Unlock", blurb: "Free time types", Icon: Unlock },
  { id: "day", label: "Day", blurb: "Body, sleep, ZeppBridge, plan", Icon: SunMedium },
  { id: "appearance", label: "Appearance", blurb: "Theme, UI, sidebar look", Icon: Palette },
  { id: "profile", label: "Profile", blurb: "Name, email, notes", Icon: CircleUserRound },
  { id: "data", label: "Data", blurb: "Export, import, update", Icon: Database },
  { id: "advanced", label: "Advanced", blurb: "AI, remote, tools", Icon: Settings2 },
];

const WRITE_SECTIONS: SettingsSectionId[] = [
  "blocks",
  "sites",
  "apps",
  "limits",
  "filters",
  "review",
  "unlock",
];

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={cn("settings-chrome__card", className)}>{children}</div>;
}

function SectionHeader({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="mb-5">
      <h2 className="text-[1.05rem] font-semibold tracking-tight text-foreground">{title}</h2>
      {description ? (
        <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-muted-foreground">
          {description}
        </p>
      ) : null}
    </div>
  );
}

function JumpCard({
  kicker,
  title,
  blurb,
  Icon,
  onClick,
}: {
  kicker: string;
  title: string;
  blurb: string;
  Icon: LucideIcon;
  onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick} className="settings-chrome__jump-btn">
      <span className="settings-chrome__jump-kicker">
        <Icon size={12} aria-hidden />
        {kicker}
      </span>
      <p className="settings-chrome__jump-title">{title}</p>
      <p className="settings-chrome__jump-blurb">{blurb}</p>
    </button>
  );
}

function softlandModeLabel(softland: ReturnType<typeof useFocusStatus>["softland"]): string {
  if (!softland) return "—";
  if (!softland.softland_enabled) return "off";
  const rt = softland.runtime || {};
  if (rt.bedtime_active) return "study (bedtime)";
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
      <FocusAiStatusChip ping compact />
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

      <div className="space-y-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#0b6b63]">
          Jobs
        </p>
        <h2 className="text-[1.15rem] font-semibold tracking-tight text-foreground">
          What do you need to change?
        </h2>
        <p className="max-w-xl text-[13px] leading-relaxed text-muted-foreground">
          Site block and Arm never share a switch. Morning path is Bible → Plan → Apply/Confirm —
          locks wait for a free day or pass.
        </p>
      </div>

      <WeaponCallout onEditSites={() => onJump("sites")} onEditArm={() => onJump("apps")} />

      <Card className="space-y-3">
        <p className="text-[15px] font-semibold text-foreground">Day flow</p>
        <ol className="list-decimal space-y-1.5 pl-5 text-[13px] leading-relaxed text-muted-foreground">
          <li>Bible chapter opens the morning gate.</li>
          <li>Plan tab: Apply routines / edit blocks → Confirm (prefs sheet on the gate).</li>
          <li>Hit the daily goal under Unlock; sites free for the rest of the day.</li>
        </ol>
      </Card>

      <div className="settings-chrome__jump">
        <JumpCard
          kicker="Lists"
          Icon={Shield}
          title="Blocks"
          blurb="Unified Focus / Normal / Block board, time limits, hosts."
          onClick={() => onJump("sites")}
        />
        <JumpCard
          kicker="Freedom"
          Icon={Unlock}
          title="Unlock"
          blurb="How free SoftLand time works — goal, reward, pass."
          onClick={() => onJump("unlock")}
        />
        <JumpCard
          kicker="Rhythm"
          Icon={SunMedium}
          title="Day"
          blurb="Body care, watch sync, plan reminders."
          onClick={() => onJump("day")}
        />
        <JumpCard
          kicker="Look"
          Icon={Palette}
          title="Appearance"
          blurb="Theme, light/dark, surfaces, sidebar title."
          onClick={() => onJump("appearance")}
        />
        <JumpCard
          kicker="You"
          Icon={CircleUserRound}
          title="Profile"
          blurb="Display name, email, notes on this PC."
          onClick={() => onJump("profile")}
        />
        <JumpCard
          kicker="Backup"
          Icon={Database}
          title="Data"
          blurb="Export, SoftLand import, UI update."
          onClick={() => onJump("data")}
        />
        <JumpCard
          kicker="Optional"
          Icon={Settings2}
          title="Advanced"
          blurb="LLM/Jarvis, Telegram, activity review."
          onClick={() => onJump("advanced")}
        />
      </div>
    </div>
  );
}

function BlocksSection({
  sub,
  onSubChange,
  onPolicySaved,
  reviewContent,
}: {
  sub: BlockSubId;
  onSubChange: (id: BlockSubId) => void;
  onPolicySaved?: () => void;
  reviewContent?: ReactNode;
}) {
  const tabs: { id: BlockSubId; label: string; note: string }[] = [
    { id: "board", label: "Board", note: "sites + apps" },
    { id: "review", label: "Review", note: "classify" },
  ];

  return (
    <div className="space-y-4">
      <SectionHeader
        title="Blocks"
        description="Edit sites and apps here. Site block On/Off and Arm live under Unlock."
      />
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
            onClick={() => onSubChange(blockSubToSection(t.id))}
            className={cn(
              "min-h-11 px-1 pb-2 text-[15px] transition-colors -mb-px",
              sub === t.id
                ? "border-b-[3px] border-[#0B6B63] font-semibold text-[#7DCFC4]"
                : "border-b-[3px] border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}{" "}
            <span className="text-[12px] font-normal opacity-70">{t.note}</span>
          </button>
        ))}
      </div>

      {sub === "board" ? (
        <div className="space-y-4">
          <Card className="min-w-0 overflow-hidden">
            <BlocksBoardPanel />
          </Card>

          <details className="rounded-xl border border-border/40 bg-background/20 open:pb-1 group">
            <summary className="cursor-pointer list-none px-3 py-2.5 text-[13px] font-medium marker:content-none [&::-webkit-details-marker]:hidden flex items-center justify-between gap-2">
              <span>Device hosts lock</span>
              <span className="text-[11px] font-normal text-muted-foreground group-open:hidden">
                porn · PC-wide · admin
              </span>
            </summary>
            <div className="border-t border-border/30 px-3 py-3">
              <DeviceBlockPanel />
            </div>
          </details>
        </div>
      ) : null}

      {sub === "review" ? (
        <div className="space-y-4">
          <p className="text-[13px] text-muted-foreground">
            Classify what ran, then put apps on the Board or a Limit. Labels never arm SoftLand or Arm.
          </p>
          {reviewContent ?? (
            <p className="text-[13px] text-muted-foreground">Activity review unavailable here.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}

function UnlockSection({ onPolicySaved }: { onPolicySaved?: () => void }) {
  return (
    <div className="space-y-5">
      <SectionHeader
        title="Unlock"
        description="Site block and Arm masters live here. SoftLand free ≠ Arm. Lists and limits stay on Blocks → Board."
      />
      <div className="grid gap-3 min-w-0 md:grid-cols-2">
        <Card className="min-w-0 overflow-hidden !p-3">
          <div className="mb-2 flex items-baseline justify-between gap-2">
            <h3 className="text-[13px] font-semibold">Site block</h3>
            <span className="text-[11px] text-muted-foreground">SoftLand · sites only</span>
          </div>
          <ProductivityPolicyPanel variant="softland" onSaved={onPolicySaved} />
        </Card>
        <Card className="min-w-0 overflow-hidden !p-3">
          <div className="mb-2 flex items-baseline justify-between gap-2">
            <h3 className="text-[13px] font-semibold">Arm</h3>
            <span className="text-[11px] text-muted-foreground">apps · bedtime keeps kills</span>
          </div>
          <ArmControlCard />
        </Card>
      </div>
      <Card className="min-w-0 overflow-hidden">
        <UnlockGuidePanel onSaved={onPolicySaved} />
      </Card>
    </div>
  );
}

type MakeSettingsAppProps = {
  section?: SettingsSectionId;
  onSectionChange?: (id: SettingsSectionId) => void;
  onPolicySaved?: () => void;
  dayContent?: ReactNode;
  profileContent?: ReactNode;
  dataContent?: ReactNode;
  advancedContent?: ReactNode;
  /** Blocks → Review (classify + day activities). */
  reviewContent?: ReactNode;
  /** @deprecated use day/data/advanced slots */
  productiveExtra?: ReactNode;
  /** @deprecated use day/data/advanced slots */
  toolsContent?: ReactNode;
};

function navHighlight(section: SettingsSectionId): NavId {
  if (
    section === "sites" ||
    section === "apps" ||
    section === "limits" ||
    section === "filters" ||
    section === "review" ||
    section === "blocks"
  )
    return "blocks";
  if (section === "day" || section === "tools" || section === "more") return "day";
  if (section === "appearance") return "appearance";
  if (section === "profile") return "profile";
  if (section === "data") return "data";
  if (section === "advanced" || section === "productive") return "advanced";
  if (section === "unlock") return "unlock";
  return "overview";
}

function blockSubFromSection(section: SettingsSectionId): BlockSubId {
  if (section === "review") return "review";
  // sites / apps / limits / filters / blocks → one Board page
  return "board";
}

function blockSubToSection(sub: BlockSubId): SettingsSectionId {
  if (sub === "review") return "review";
  return "sites"; // board
}

function navClickTarget(id: NavId): SettingsSectionId {
  if (id === "blocks") return "sites";
  return id;
}

export default function MakeSettingsApp({
  section: sectionProp,
  onSectionChange,
  onPolicySaved,
  dayContent,
  profileContent,
  dataContent,
  advancedContent,
  reviewContent,
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

  // Back-compat: old single tools dump still renders under Day if new slots unused.
  const dayBody = dayContent ?? toolsContent;
  const advancedBody = (
    <>
      {advancedContent}
      {productiveExtra}
    </>
  );

  const body =
    highlight === "overview" ? (
      <OverviewSection onJump={setSection} />
    ) : highlight === "blocks" ? (
      <BlocksSection
        sub={blockSub}
        onSubChange={(id) => setSection(id)}
        onPolicySaved={onPolicySaved}
        reviewContent={reviewContent}
      />
    ) : highlight === "unlock" ? (
      <UnlockSection onPolicySaved={onPolicySaved} />
    ) : highlight === "day" ? (
      <div>
        <SectionHeader
          title="Day"
          description="Body care, wearables, and plan preferences for the daily loop."
        />
        {dayBody}
      </div>
    ) : highlight === "appearance" ? (
      <div>
        <SectionHeader
          title="Appearance"
          description="Theme, light/dark, surfaces, and the sidebar title sticker. All UI look lives here."
        />
        <ThemeSettingsPanel embedded />
        <div className="mt-6 gloss-panel rounded-xl border border-border/50 p-5">
          <SidebarTitleStickerPanel />
        </div>
      </div>
    ) : highlight === "profile" ? (
      <div>
        <SectionHeader
          title="Profile"
          description="Who owns this Focus install — name and notes stay on this PC."
        />
        {profileContent}
      </div>
    ) : highlight === "data" ? (
      <div>
        <SectionHeader
          title="Data"
          description="Export analytics, import SoftLand site lists, check for Focus UI updates."
        />
        {dataContent}
      </div>
    ) : (
      <div>
        <SectionHeader
          title="Advanced"
          description="Optional AI voice, remote control, and activity classification. Safe to ignore."
        />
        <div className="mb-5">
          <FocusPerfReviewPanel />
        </div>
        {advancedBody}
      </div>
    );

  return (
    <div className="settings-chrome settings-chrome__shell text-foreground">
      <aside className="settings-chrome__rail" aria-label="Settings navigation">
        <div className="settings-chrome__brand">
          <h1>Settings</h1>
          <p>Site block and Arm are separate. Turning one on never turns on the other.</p>
        </div>
        <nav className="settings-chrome__nav" aria-label="Settings sections">
          {NAV.map(({ id, label, blurb, Icon }) => {
            const active = highlight === id;
            return (
              <button
                key={id}
                type="button"
                aria-current={active ? "page" : undefined}
                onClick={() => setSection(navClickTarget(id))}
                className={cn("settings-chrome__nav-btn", active && "is-active")}
              >
                <Icon size={16} className="settings-chrome__nav-icon" aria-hidden />
                <span className="min-w-0">
                  <span className="settings-chrome__nav-label">{label}</span>
                  <span className="settings-chrome__nav-blurb">{blurb}</span>
                </span>
              </button>
            );
          })}
        </nav>
      </aside>

      <div className="settings-chrome__main">
        {isFocusDesktopShell() ? (
          <div className="settings-chrome__status">
            <LiveStatusStrip />
          </div>
        ) : null}
        <main className="settings-chrome__body">
          {WRITE_SECTIONS.includes(section) || highlight === "blocks" ? (
            <EnforcerWriteGate>{body}</EnforcerWriteGate>
          ) : (
            body
          )}
        </main>
      </div>
    </div>
  );
}

export function parseSettingsSection(raw: string | null): SettingsSectionId {
  const id = (raw || "overview").toLowerCase();

  if (id === "blocks") return "sites";
  if (id === "more" || id === "tools") return "day";
  if (id === "productive" || id === "scoring") return "advanced";
  if (id === "classification" || id === "classify" || id === "activity") return "review";
  if (id === "theme" || id === "ui" || id === "look" || id === "sticker") return "appearance";
  if (id === "timelimits" || id === "time-limits" || id === "app-limits") return "sites";
  if (id === "limits" || id === "filters") return "sites";

  const known: SettingsSectionId[] = [
    "overview",
    "sites",
    "apps",
    "review",
    "unlock",
    "day",
    "appearance",
    "profile",
    "data",
    "advanced",
  ];
  if (known.includes(id as SettingsSectionId)) return id as SettingsSectionId;

  // Legacy hub / Make rail ids
  if (id === "now" || id === "focus" || id === "enforcer") return "unlock";
  if (id === "rules" || id === "policy" || id === "schedules") return "sites";
  if (
    id === "watch" ||
    id === "reminders" ||
    id === "planning" ||
    id === "body" ||
    id === "bodycare"
  ) {
    return "day";
  }
  if (id === "account" || id === "owner" || id === "me" || id === "user") return "profile";
  if (id === "export" || id === "import" || id === "update" || id === "setup") return "data";
  if (id === "demo" || id === "demo-mode" || id === "jarvis" || id === "llm" || id === "telegram") {
    return "advanced";
  }
  return "overview";
}
