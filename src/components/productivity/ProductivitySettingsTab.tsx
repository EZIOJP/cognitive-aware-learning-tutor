import type { ReactNode } from "react";
import { Download, Loader2, Terminal } from "lucide-react";
import { DemoModePanel } from "./DemoModePanel";
import { WearablesSyncPanel } from "./WearablesSyncPanel";
import { PlannerRemindersPanel } from "./PlannerRemindersPanel";
import { FocusLlmHostPanel } from "./FocusLlmHostPanel";
import { FocusJarvisPanel } from "./FocusJarvisPanel";
import { FocusOpenJarvisPanel } from "./FocusOpenJarvisPanel";
import { FocusTelegramRemotePanel } from "./FocusTelegramRemotePanel";
import { FocusEmailReportPanel } from "./FocusEmailReportPanel";
import { QuitHowToPanel } from "./QuitHowToPanel";
import { PlanningSettingsPanel } from "./PlanningSettingsPanel";
import { SessionOverridePanel } from "./SessionOverridePanel";
import { ActivitiesPanel } from "./ActivitiesPanel";
import ClassificationReview from "./ClassificationReview";
import { ExportRangeCalendar } from "./ExportRangeCalendar";
import { FocusImportUpdatePanel } from "./FocusImportUpdatePanel";
import { BodyCarePanel } from "./BodyCarePanel";
import { DesktopManagedBanner } from "./DesktopManagedBanner";
import { FocusOwnerProfilePanel } from "./FocusOwnerProfilePanel";
import MakeSettingsApp, {
  parseSettingsSection,
  type SettingsSectionId,
} from "./settings/make/MakeSettingsApp";
import type { DesktopTimeline } from "../../api/behaviorClient";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";

export type ProductivitySettingsTabProps = {
  section: SettingsSectionId;
  onSectionChange: (id: SettingsSectionId) => void;
  plannerRefresh: number;
  bumpPlanner: () => void;
  onPolicySaved: () => void;
  timeline: DesktopTimeline | null;
  plannerDayApi: string;
  trackerNoData: boolean;
  onLoad: () => void;
  onDemoChanged: () => void;
  onJumpToDay: (day: Date) => void;
  exportHint: string | null;
  exportDays: number;
  exportStartDay: string;
  exportEndDay: string;
  exporting: boolean;
  applyExportWindow: (start: string, end: string) => void;
  setExportDaysWindow: (days: number, end: string) => void;
  exportWeek: (fmt: "json" | "csv" | "csv_wide") => void;
  toApiDay: (d: Date) => string;
};

function Chunk({
  title,
  children,
  hint,
}: {
  title: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <div className="settings-chrome__card space-y-3">
      <div>
        <h3 className="text-[15px] font-semibold text-foreground tracking-tight">{title}</h3>
        {hint ? (
          <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{hint}</p>
        ) : null}
      </div>
      {children}
    </div>
  );
}

export function ProductivitySettingsTab(props: ProductivitySettingsTabProps) {
  const focusShell = isFocusDesktopShell();

  const dayContent: ReactNode = (
    <div className="space-y-6">
      <BodyCarePanel />
      <Chunk title="Watch ↔ PC" hint="ZeppBridge pull preferred; CALT Sync optional.">
        <WearablesSyncPanel />
      </Chunk>
      <Chunk title="Plan reminders">
        <PlannerRemindersPanel />
      </Chunk>
      <Chunk title="Planning" hint="Morning Confirm and related day-loop prefs.">
        <PlanningSettingsPanel
          refreshKey={props.plannerRefresh}
          onPlannerChange={props.bumpPlanner}
        />
      </Chunk>
    </div>
  );

  const dataContent: ReactNode = (
    <div className="space-y-6">
      <Chunk title="Export">
        {props.exportHint ? (
          <span className="inline-block max-w-full truncate rounded-full border border-sky-500/25 bg-sky-500/10 px-3 py-1 text-xs text-sky-300">
            {props.exportHint}
          </span>
        ) : null}
        <div className="flex flex-wrap gap-1.5">
          {([7, 30, 90, 365] as const).map((days) => (
            <button
              key={days}
              type="button"
              onClick={() => props.setExportDaysWindow(days, props.toApiDay(new Date()))}
              className={`rounded-full border px-3 py-1 text-xs ${
                props.exportDays === days
                  ? "border-primary/30 bg-primary/10 text-primary"
                  : "border-border/50 bg-background/35 text-muted-foreground"
              }`}
            >
              {days === 365 ? "Year" : `${days}d`}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2 max-w-md">
          <label className="block space-y-1 text-xs text-muted-foreground">
            <span>From</span>
            <input
              type="date"
              value={props.exportStartDay}
              onChange={(e) => props.applyExportWindow(e.target.value, props.exportEndDay)}
              className="w-full rounded-lg border border-border/50 bg-background/50 px-2 py-1.5 text-xs"
            />
          </label>
          <label className="block space-y-1 text-xs text-muted-foreground">
            <span>To</span>
            <input
              type="date"
              value={props.exportEndDay}
              onChange={(e) => props.applyExportWindow(props.exportStartDay, e.target.value)}
              className="w-full rounded-lg border border-border/50 bg-background/50 px-2 py-1.5 text-xs"
            />
          </label>
        </div>
        <ExportRangeCalendar
          startIso={props.exportStartDay}
          endIso={props.exportEndDay}
          onRangeChange={(start, end) => props.applyExportWindow(start, end)}
        />
        <p className="text-[11px] text-muted-foreground leading-relaxed max-w-lg">
          Saves to your Downloads folder in Focus desktop (JSON / CSV).
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={props.exporting}
            onClick={() => void props.exportWeek("json")}
            className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-background/35 px-3 py-2 text-xs hover:bg-accent/50 disabled:opacity-50"
          >
            {props.exporting ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
            JSON
          </button>
          <button
            type="button"
            disabled={props.exporting}
            onClick={() => void props.exportWeek("csv")}
            className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-background/35 px-3 py-2 text-xs hover:bg-accent/50 disabled:opacity-50"
          >
            <Download size={13} /> CSV (long)
          </button>
          <button
            type="button"
            disabled={props.exporting}
            onClick={() => void props.exportWeek("csv_wide")}
            className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-background/35 px-3 py-2 text-xs hover:bg-accent/50 disabled:opacity-50"
          >
            <Download size={13} /> CSV (wide)
          </button>
        </div>
      </Chunk>

      <FocusImportUpdatePanel />

      <div className="space-y-2 rounded-xl border border-border/50 bg-background/35 p-4">
        <h3 className="font-semibold flex items-center gap-2 text-sm">
          <Terminal size={15} className="text-sky-400" />
          Setup
        </h3>
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Edge SelfTracker + CALT Gate for SoftLand.{" "}
          <code className="text-[10px] bg-black/40 px-1 rounded">
            scripts\desktop_tracker\run\run_calt_desktop.bat
          </code>{" "}
          for Focus + enforcer. Arm lives under <strong className="text-foreground/80">Unlock</strong>.
        </p>
      </div>
    </div>
  );

  const advancedContent: ReactNode = (
    <div className="space-y-6">
      <Chunk title="Voice & LLM" hint="Optional. Home brief / Jarvis use this when enabled.">
        <div className="space-y-4">
          <FocusLlmHostPanel />
          <FocusJarvisPanel variant="settings" />
        </div>
      </Chunk>

      <details className="rounded-xl border border-border/50 bg-background/25 p-4 group">
        <summary className="cursor-pointer text-sm font-medium list-none flex items-center justify-between">
          Remote & email
          <span className="text-[11px] text-muted-foreground font-normal group-open:hidden">
            Telegram · daily mail · OpenJarvis
          </span>
        </summary>
        <div className="mt-4 space-y-4">
          <FocusTelegramRemotePanel />
          <FocusEmailReportPanel />
          <FocusOpenJarvisPanel />
        </div>
      </details>

      {focusShell ? (
        <Chunk title="Quit">
          <QuitHowToPanel />
        </Chunk>
      ) : null}

      {!focusShell ? (
        <Chunk title="Demo mode" hint="Fake SoftLand clock for testing. Leave off for real days.">
          <DemoModePanel onChanged={props.onDemoChanged} onJumpToDay={props.onJumpToDay} />
        </Chunk>
      ) : null}

      <details className="rounded-xl border border-border/50 bg-background/25 p-4 group">
        <summary className="cursor-pointer text-sm font-medium list-none flex items-center justify-between">
          Activity review
          <span className="text-[11px] text-muted-foreground font-normal group-open:hidden">
            Day table · classify
          </span>
        </summary>
        <div className="mt-4 space-y-4">
          <DesktopManagedBanner feature="Activity review" />
          <div className="rounded-2xl border border-border/50 bg-card/30 p-4 sm:p-6">
            <ActivitiesPanel
              day={props.plannerDayApi}
              trackerNoData={props.trackerNoData}
              refreshKey={props.plannerRefresh}
            />
          </div>
          <div className="rounded-2xl border border-border/50 bg-card/30 p-4 sm:p-6">
            <ClassificationReview trackerNoData={props.trackerNoData} />
          </div>
          {!focusShell ? (
            <div className="rounded-2xl border border-border/50 bg-card/30 p-4 sm:p-6 space-y-2">
              <p className="text-[11px] text-muted-foreground">
                Session override needs Study API — hidden in Focus desktop.
              </p>
              <SessionOverridePanel
                timeline={props.timeline}
                onSaved={() => {
                  props.onLoad();
                  props.bumpPlanner();
                }}
              />
            </div>
          ) : (
            <p className="text-[11px] text-muted-foreground px-1">
              Session productive override is Study-only (needs <code className="text-[10px]">:8000</code>
              ). Focus uses day activities + OpenJarvis classify when enabled.
            </p>
          )}
        </div>
      </details>
    </div>
  );

  return (
    <div className="focus-panel settings-no-scrollbar min-h-0 w-full overflow-visible">
      <MakeSettingsApp
        section={props.section}
        onSectionChange={props.onSectionChange}
        onPolicySaved={props.onPolicySaved}
        dayContent={dayContent}
        profileContent={
          <div className="settings-chrome__card">
            <FocusOwnerProfilePanel />
          </div>
        }
        dataContent={dataContent}
        advancedContent={advancedContent}
      />
    </div>
  );
}

export { parseSettingsSection };
export type { SettingsSectionId };
