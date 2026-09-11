import { useState, type ReactNode } from "react";

// ── types ──────────────────────────────────────────────────────────────────

type Section = "overview" | "rules" | "unlock" | "productive" | "tools";
type ToolTab = "watch" | "export" | "other";

type RuleEntry = {
  id: string;
  value: string; // domain or exe
  type: "site" | "app";
  list: "allow" | "watch" | "block"; // for sites: allow/watch/block; apps are always "block"
};

interface ScheduleWindow {
  id: string;
  days: number[];
  start: string;
  end: string;
  mode: "study" | "free";
}

interface AppState {
  softlandEnabled: boolean;
  armed: boolean;
  mode: "study" | "free" | "incubating";
  modeUntil: string;
  earnedMinutes: number;
  goalMinutes: number;
  productiveMinutes: number;
  chapterDone: boolean;
  rewardDays: number;
  rules: RuleEntry[];
  schedules: ScheduleWindow[];
  blockPorn: boolean;
  blockWatchSites: boolean;
  lockMode: "none" | "timer" | "password" | "phrase";
  studyLoopGate: boolean;
  threshold: number;
}

// ── primitives ─────────────────────────────────────────────────────────────

function Badge({
  children,
  variant = "default",
}: {
  children: ReactNode;
  variant?: "default" | "danger" | "success" | "warn" | "muted" | "api" | "site" | "app" | "system";
}) {
  const colors: Record<string, string> = {
    default: "bg-muted text-muted-foreground border border-border/50",
    danger: "bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/30",
    success: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30",
    warn: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/30",
    muted: "bg-muted/60 text-muted-foreground border border-border/40",
    api: "bg-primary/10 text-primary border border-primary/25",
    site: "bg-sky-500/10 text-sky-700 dark:text-sky-400 border border-sky-500/25",
    app: "bg-violet-500/10 text-violet-700 dark:text-violet-400 border border-violet-500/25",
    system: "bg-amber-500/10 text-amber-700/80 dark:text-amber-500/80 border border-amber-500/20",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-mono font-medium tracking-wide ${colors[variant]}`}
    >
      {children}
    </span>
  );
}

function Toggle({
  checked,
  onChange,
  danger = false,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      style={{ height: "22px" }}
      className={`relative w-10 rounded-full transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-primary/40 ${
        checked ? (danger ? "bg-rose-600" : "bg-primary") : "bg-muted"
      }`}
    >
      <span
        style={{ width: "18px", height: "18px" }}
        className={`absolute top-0.5 left-0.5 bg-background rounded-full shadow transition-transform duration-150 ${
          checked ? "translate-x-[18px]" : "translate-x-0"
        }`}
      />
    </button>
  );
}

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
    <div className="mb-6">
      <div className="flex items-center gap-3 mb-1">
        <h2 className="text-[15px] font-semibold text-foreground tracking-tight">{title}</h2>
        {badge}
      </div>
      {description && (
        <p className="text-[12px] text-muted-foreground leading-relaxed">{description}</p>
      )}
    </div>
  );
}

function SettingRow({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-3.5 border-b border-border/40 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="text-[13px] text-foreground font-medium">{label}</div>
        {description && (
          <div className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">{description}</div>
        )}
      </div>
      {children && <div className="flex-shrink-0">{children}</div>}
    </div>
  );
}

function NeedsApiBadge() {
  return (
    <Badge variant="api">
      <span>⚡</span> Needs API
    </Badge>
  );
}

const DAY_LABELS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

function DayPills({ selected, onChange }: { selected: number[]; onChange: (d: number[]) => void }) {
  const toggle = (d: number) =>
    onChange(selected.includes(d) ? selected.filter((x) => x !== d) : [...selected, d]);
  return (
    <div className="flex gap-1">
      {DAY_LABELS.map((label, i) => (
        <button
          key={i}
          type="button"
          onClick={() => toggle(i)}
          className={`w-8 h-7 rounded-lg text-[10px] font-mono font-medium transition-colors ${
            selected.includes(i)
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground hover:text-foreground"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

// ── Overview ───────────────────────────────────────────────────────────────

function OverviewSection({ state, set }: { state: AppState; set: (s: Partial<AppState>) => void }) {
  const [armPhrase, setArmPhrase] = useState("");
  const goalPct = Math.min(100, Math.round((state.productiveMinutes / state.goalMinutes) * 100));

  const modeBg =
    state.mode === "study"
      ? "bg-amber-500/10 border-amber-500/25"
      : state.mode === "free"
        ? "bg-emerald-500/10 border-emerald-500/25"
        : "bg-rose-500/10 border-rose-500/25";
  const modeColor =
    state.mode === "study" ? "text-amber-700 dark:text-amber-400" : state.mode === "free" ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400";

  return (
    <div>
      <SectionHeader title="Overview" description="Live status, Plan block, and controls." />

      {/* two weapons */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-sky-500/10 border border-sky-500/25 rounded-xl p-4">
          <div className="text-[9px] font-mono text-primary tracking-[0.2em] uppercase mb-2">SoftLand</div>
          <div className="text-[12px] text-foreground font-medium mb-1">Blocks websites</div>
          <div className="text-[10px] text-muted-foreground leading-relaxed">
            Stateful by mode — same site allowed or blocked depending on schedule,
            reward day, or incubation. Never kills apps.
          </div>
        </div>
        <div className="bg-rose-500/10 border border-rose-500/25 rounded-xl p-4">
          <div className="text-[9px] font-mono text-rose-700 dark:text-rose-400 tracking-[0.2em] uppercase mb-2">Arm</div>
          <div className="text-[12px] text-foreground font-medium mb-1">Kills apps at OS level</div>
          <div className="text-[10px] text-muted-foreground leading-relaxed">
            calt_enforcer terminates listed .exe every ~1.5s. Never touches URLs.
            SoftLand ON ≠ Armed.
          </div>
        </div>
      </div>

      {/* status strip */}
      <div className={`border rounded-xl p-4 mb-4 ${modeBg}`}>
        <div className="grid grid-cols-4 gap-4 mb-3">
          <div>
            <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest mb-1">Mode</div>
            <div className={`text-[15px] font-semibold capitalize ${modeColor}`}>{state.mode}</div>
          </div>
          <div>
            <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest mb-1">Until</div>
            <div className="text-[13px] font-mono text-muted-foreground">{state.modeUntil}</div>
          </div>
          <div>
            <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest mb-1">SoftLand</div>
            <Badge variant={state.softlandEnabled ? "success" : "muted"}>
              {state.softlandEnabled ? "ON" : "OFF"}
            </Badge>
          </div>
          <div>
            <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest mb-1">Arm</div>
            <Badge variant={state.armed ? "danger" : "muted"}>
              {state.armed ? "ARMED" : "DISARMED"}
            </Badge>
          </div>
        </div>
        <div className="text-[10px] text-muted-foreground">
          {state.mode === "study" && "Watch sites blocked · Steam.exe killed if Armed · filter always blocked"}
          {state.mode === "free" && "Watch sites open · block_extra and filter still blocked · Arm still active if armed"}
          {state.mode === "incubating" && "Forced study mode · spending earned minutes refused · 8 min cooldown"}
        </div>
      </div>

      {/* plan + goal */}
      <Card className="mb-4">
        <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase mb-3">Plan — now</div>
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="text-[14px] font-medium text-foreground">Deep Work: GRE Quant</div>
            <div className="text-[11px] text-muted-foreground mt-0.5">Ends 15:30 · 47 min left · Next: Bible + Review</div>
          </div>
          <div className="text-right">
            <div className="text-[9px] font-mono text-muted-foreground">Goal</div>
            <div className="text-[12px] font-mono text-muted-foreground">{state.productiveMinutes}/{state.goalMinutes} min</div>
          </div>
        </div>
        <div className="w-full bg-muted rounded-full h-1 mb-1">
          <div className="bg-primary h-1 rounded-full transition-all" style={{ width: `${goalPct}%` }} />
        </div>
        <div className="flex justify-between">
          <span className="text-[10px] font-mono text-muted-foreground/70">{goalPct}% toward unlock</span>
          <span className="text-[10px] font-mono text-muted-foreground/70">{state.goalMinutes - state.productiveMinutes} min left</span>
        </div>
      </Card>

      {/* earned + arm side by side */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <Card>
          <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase mb-2">Earned minutes</div>
          <div className="text-[22px] font-mono font-medium text-foreground mb-1">{state.earnedMinutes}</div>
          <div className="text-[10px] text-muted-foreground mb-3">in ledger · cap 60/day</div>
          <button
            disabled={state.earnedMinutes < 15 || state.mode === "incubating"}
            onClick={() => set({ earnedMinutes: Math.max(0, state.earnedMinutes - 15) })}
            className="w-full py-1.5 bg-muted hover:bg-accent/60 disabled:opacity-30 disabled:cursor-not-allowed border border-border/50 rounded text-[11px] text-muted-foreground transition-colors"
          >
            Spend 15 min
          </button>
          {state.mode === "incubating" && (
            <div className="mt-1.5 text-[9px] text-rose-600/70 dark:text-rose-400/60 font-mono text-center">refused during incubation</div>
          )}
        </Card>

        <Card>
          <div className="flex items-center justify-between mb-2">
            <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase">Arm</div>
            <Badge variant={state.armed ? "danger" : "muted"}>{state.armed ? "ARMED" : "DISARMED"}</Badge>
          </div>
          <div className="text-[10px] text-muted-foreground mb-3 leading-relaxed">
            OS kill loop · ~1.5s · {state.armed ? `${["Steam.exe","Discord.exe"].length} targets` : "Inactive"}
          </div>
          {state.armed ? (
            <div className="space-y-1.5">
              <input
                value={armPhrase}
                onChange={(e) => setArmPhrase(e.target.value)}
                placeholder='Type "DISARM"'
                className="w-full px-2.5 py-1.5 bg-background/50 border border-border/50 rounded text-[11px] font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-border"
              />
              <button
                disabled={armPhrase !== "DISARM"}
                onClick={() => { set({ armed: false }); setArmPhrase(""); }}
                className="w-full py-1.5 bg-rose-500/10 disabled:opacity-30 disabled:cursor-not-allowed border border-rose-500/40 rounded text-[11px] text-rose-600 dark:text-rose-400 transition-colors hover:bg-rose-500/20"
              >
                Disarm
              </button>
            </div>
          ) : (
            <button
              onClick={() => set({ armed: true })}
              className="w-full py-1.5 bg-rose-600/90 hover:bg-rose-600 border border-rose-500/40 rounded text-[11px] text-rose-600 dark:text-rose-400 font-medium transition-colors"
            >
              Arm
            </button>
          )}
        </Card>
      </div>

      <div className="p-3 bg-background/50 border border-border/40 rounded text-[10px] text-muted-foreground/70 leading-relaxed">
        <span className="text-primary/80 font-mono">Offline-native:</span> SoftLand, Arm, lists, schedules, ledger — no :8000 needed. &nbsp;
        <span className="text-primary/60 font-mono">Needs API:</span> scores, classification.
      </div>
    </div>
  );
}

// ── Rules ──────────────────────────────────────────────────────────────────

type RulesTab = "list" | "schedules";

const BUILTIN_WATCH = [
  "youtube.com", "netflix.com", "primevideo.com", "twitch.tv",
  "reddit.com", "twitter.com", "instagram.com", "tiktok.com", "discord.com",
];

function RulesSection({ state, set }: { state: AppState; set: (s: Partial<AppState>) => void }) {
  const [tab, setTab] = useState<RulesTab>("list");
  const [addType, setAddType] = useState<"site" | "app">("site");
  const [addList, setAddList] = useState<"allow" | "watch" | "block">("block");
  const [addValue, setAddValue] = useState("");
  const [filter, setFilter] = useState<"all" | "site" | "app">("all");

  const addRule = () => {
    const v = addValue.trim().toLowerCase();
    if (!v) return;
    const newRule: RuleEntry = {
      id: Date.now().toString(),
      value: v,
      type: addType,
      list: addType === "app" ? "block" : addList,
    };
    set({ rules: [...state.rules, newRule] });
    setAddValue("");
  };

  const removeRule = (id: string) =>
    set({ rules: state.rules.filter((r) => r.id !== id) });

  const filtered = state.rules.filter((r) => filter === "all" || r.type === filter);

  // for each rule, compute what happens in each mode
  const ruleStatus = (r: RuleEntry): Record<"study" | "free" | "incubating", "blocked" | "allowed" | "killed"> => {
    if (r.type === "app") {
      const k = state.armed ? "killed" : "allowed";
      return { study: k, free: k, incubating: k };
    }
    if (r.list === "allow") return { study: "allowed", free: "allowed", incubating: "allowed" };
    if (r.list === "block") return { study: "blocked", free: "blocked", incubating: "blocked" };
    // watch: blocked in study/incubating, allowed in free
    return { study: "blocked", free: "allowed", incubating: "blocked" };
  };

  return (
    <div>
      <SectionHeader
        title="Rules"
        description="Combined block list — websites (SoftLand) and apps (Arm). Filter runs as a permanent system rule."
      />

      {/* sub-tabs */}
      <div className="flex gap-1 mb-5 rounded-xl border border-border/50 bg-background/35 p-1">
        {(["list", "schedules"] as RulesTab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`flex-1 py-1.5 rounded-lg text-[11px] font-medium capitalize transition-colors ${
              tab === t ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
            }`}
          >
            {t === "list" ? "Block list" : "Schedules"}
          </button>
        ))}
      </div>

      {tab === "list" && (
        <div>
          {/* add rule */}
          <Card className="mb-4">
            <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase mb-3">Add rule</div>
            <div className="flex gap-2 mb-2">
              <button
                onClick={() => setAddType("site")}
                className={`flex-1 py-1.5 rounded text-[11px] font-mono border transition-colors ${
                  addType === "site"
                    ? "bg-primary/15 border-primary/30 text-primary"
                    : "bg-muted/50 border-border/50 text-muted-foreground hover:text-muted-foreground"
                }`}
              >
                Site
              </button>
              <button
                onClick={() => setAddType("app")}
                className={`flex-1 py-1.5 rounded text-[11px] font-mono border transition-colors ${
                  addType === "app"
                    ? "bg-violet-500/15 border-violet-500/30 text-violet-700 dark:text-violet-300"
                    : "bg-muted/50 border-border/50 text-muted-foreground hover:text-muted-foreground"
                }`}
              >
                App (.exe)
              </button>
            </div>

            {addType === "site" && (
              <div className="flex gap-1.5 mb-2">
                {(["allow", "watch", "block"] as const).map((l) => (
                  <button
                    key={l}
                    onClick={() => setAddList(l)}
                    className={`flex-1 py-1 rounded text-[10px] font-mono border transition-colors ${
                      addList === l
                        ? "bg-muted border-border/60 text-foreground/80"
                        : "bg-background/50 border-border/50 text-muted-foreground/70 hover:text-muted-foreground"
                    }`}
                  >
                    {l}
                  </button>
                ))}
              </div>
            )}

            <div className="flex gap-2">
              <input
                value={addValue}
                onChange={(e) => setAddValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addRule()}
                placeholder={addType === "app" ? "Discord.exe" : addList === "allow" ? "meet.google.com" : "reddit.com"}
                className="flex-1 px-3 py-1.5 bg-background/50 border border-border/50 rounded text-[12px] font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-border/60"
              />
              <button
                onClick={addRule}
                className="px-4 py-1.5 bg-muted hover:bg-accent/60 border border-border/50 rounded text-[11px] text-muted-foreground transition-colors"
              >
                Add
              </button>
            </div>

            {addType === "site" && (
              <div className="mt-2 text-[10px] text-muted-foreground/70 leading-relaxed">
                {addList === "allow" && "Always allowed — beats every rule including the filter."}
                {addList === "watch" && "Study mode only — free and reward days let these through."}
                {addList === "block" && "Blocked in every mode including reward days."}
              </div>
            )}
          </Card>

          {/* filter pills */}
          <div className="flex gap-1.5 mb-3">
            {(["all", "site", "app"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1 rounded text-[10px] font-mono border transition-colors ${
                  filter === f
                    ? "bg-muted border-border/60 text-foreground/80"
                    : "bg-background/50 border-border/40 text-muted-foreground hover:text-muted-foreground"
                }`}
              >
                {f === "all" ? `All (${state.rules.length})` : f === "site" ? `Sites (${state.rules.filter(r => r.type === "site").length})` : `Apps (${state.rules.filter(r => r.type === "app").length})`}
              </button>
            ))}
          </div>

          {/* mode columns header */}
          {filtered.length > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 mb-1 text-[9px] font-mono text-muted-foreground/70 tracking-widest uppercase">
              <div className="flex-1">Rule</div>
              <div className="w-16 text-center">Study</div>
              <div className="w-16 text-center">Free</div>
              <div className="w-20 text-center">Incubating</div>
              <div className="w-6" />
            </div>
          )}

          {/* rule rows */}
          <div className="space-y-1">
            {filtered.map((r) => {
              const s = ruleStatus(r);
              const statusColor = (v: string) =>
                v === "blocked" ? "text-rose-600/80 dark:text-rose-400/70" :
                v === "killed" ? "text-rose-600 dark:text-rose-400" :
                "text-emerald-600/70 dark:text-emerald-400/60";
              return (
                <div
                  key={r.id}
                  className="flex items-center gap-2 px-3 py-2.5 bg-muted/40 border border-border/50 rounded-lg hover:border-border/50 transition-colors"
                >
                  <Badge variant={r.type === "site" ? "site" : "app"}>
                    {r.type === "site" ? r.list : "exe"}
                  </Badge>
                  <span className="flex-1 text-[12px] font-mono text-foreground/70 truncate">{r.value}</span>
                  <span className={`w-16 text-[10px] font-mono text-center ${statusColor(s.study)}`}>
                    {s.study}
                  </span>
                  <span className={`w-16 text-[10px] font-mono text-center ${statusColor(s.free)}`}>
                    {s.free}
                  </span>
                  <span className={`w-20 text-[10px] font-mono text-center ${statusColor(s.incubating)}`}>
                    {s.incubating}
                  </span>
                  <button
                    onClick={() => removeRule(r.id)}
                    className="w-6 text-muted-foreground/70 hover:text-muted-foreground transition-colors text-[14px] text-center"
                  >
                    ×
                  </button>
                </div>
              );
            })}

            {filtered.length === 0 && (
              <div className="text-[11px] text-muted-foreground/70 text-center py-8">
                No {filter === "all" ? "" : filter} rules yet
              </div>
            )}
          </div>

          {/* system rules — permanent, shown as readonly */}
          <div className="mt-4">
            <div className="text-[9px] font-mono text-muted-foreground/70 tracking-widest uppercase mb-2 px-1">
              System rules — always active
            </div>
            <div className="space-y-1">
              {/* system filter */}
              <div className="flex items-center gap-2 px-3 py-2.5 bg-background/50 border border-border/40 rounded-lg">
                <Badge variant="system">system</Badge>
                <span className="flex-1 text-[12px] font-mono text-muted-foreground/60">SoftLand filter · heuristic</span>
                <span className="w-16 text-[10px] font-mono text-center text-rose-700/60 dark:text-rose-400/60">blocked</span>
                <span className="w-16 text-[10px] font-mono text-center text-rose-700/60 dark:text-rose-400/60">blocked</span>
                <span className="w-20 text-[10px] font-mono text-center text-rose-700/60 dark:text-rose-400/60">blocked</span>
                <div className="w-6" />
              </div>
              {/* hosts filter */}
              <div className="flex items-center gap-2 px-3 py-2.5 bg-background/50 border border-border/40 rounded-lg">
                <Badge variant="system">system · hosts</Badge>
                <span className="flex-1 text-[12px] font-mono text-muted-foreground/60">PC-wide filter · hosts file · all apps</span>
                <span className="w-16 text-[10px] font-mono text-center text-rose-700/60 dark:text-rose-400/60">blocked</span>
                <span className="w-16 text-[10px] font-mono text-center text-rose-700/60 dark:text-rose-400/60">blocked</span>
                <span className="w-20 text-[10px] font-mono text-center text-rose-700/60 dark:text-rose-400/60">blocked</span>
                <div className="w-6" />
              </div>
              {/* built-in watch */}
              {state.blockWatchSites && BUILTIN_WATCH.slice(0, 3).map((h) => (
                <div key={h} className="flex items-center gap-2 px-3 py-2.5 bg-background/50 border border-border/40 rounded-lg">
                  <Badge variant="system">built-in watch</Badge>
                  <span className="flex-1 text-[12px] font-mono text-muted-foreground/60">{h}</span>
                  <span className="w-16 text-[10px] font-mono text-center text-rose-700/60 dark:text-rose-400/60">blocked</span>
                  <span className="w-16 text-[10px] font-mono text-center text-emerald-700/50 dark:text-emerald-400/50">allowed</span>
                  <span className="w-20 text-[10px] font-mono text-center text-rose-700/60 dark:text-rose-400/60">blocked</span>
                  <div className="w-6" />
                </div>
              ))}
              {state.blockWatchSites && BUILTIN_WATCH.length > 3 && (
                <div className="text-[10px] font-mono text-muted-foreground/50 px-3 py-1">
                  +{BUILTIN_WATCH.length - 3} more built-in watch sites
                </div>
              )}
            </div>
          </div>

          {/* softland + watch toggles */}
          <div className="mt-4 pt-4 border-t border-border/40">
            <SettingRow label="SoftLand" description="Master site switch. Off = all sites allowed.">
              <Toggle checked={state.softlandEnabled} onChange={(v) => set({ softlandEnabled: v })} />
            </SettingRow>
            <SettingRow label="Block watch sites" description="Enables the built-in watch list in study mode.">
              <Toggle checked={state.blockWatchSites} onChange={(v) => set({ blockWatchSites: v })} />
            </SettingRow>
          </div>
        </div>
      )}

      {tab === "schedules" && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="text-[11px] text-muted-foreground">
              First matching window by day + time sets the mode. No match → study.
            </div>
            <button
              onClick={() => {
                const w: ScheduleWindow = {
                  id: Date.now().toString(),
                  days: [0, 1, 2, 3, 4],
                  start: "09:00",
                  end: "17:00",
                  mode: "study",
                };
                set({ schedules: [...state.schedules, w] });
              }}
              className="px-3 py-1.5 bg-muted hover:bg-accent/60 border border-border/50 rounded text-[10px] text-muted-foreground transition-colors"
            >
              + Add window
            </button>
          </div>
          <div className="space-y-3">
            {state.schedules.map((w) => (
              <div key={w.id} className="bg-muted/40 border border-border/50 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <select
                      value={w.mode}
                      onChange={(e) =>
                        set({ schedules: state.schedules.map((s) => s.id === w.id ? { ...s, mode: e.target.value as "study" | "free" } : s) })
                      }
                      className="bg-muted/50 border border-border/50 rounded px-2 py-1 text-[11px] font-mono text-muted-foreground focus:outline-none"
                    >
                      <option value="study">study</option>
                      <option value="free">free</option>
                    </select>
                    <input
                      value={w.start}
                      onChange={(e) =>
                        set({ schedules: state.schedules.map((s) => s.id === w.id ? { ...s, start: e.target.value } : s) })
                      }
                      className="w-20 bg-muted/50 border border-border/50 rounded px-2 py-1 text-[11px] font-mono text-muted-foreground focus:outline-none"
                    />
                    <span className="text-muted-foreground/50">–</span>
                    <input
                      value={w.end}
                      onChange={(e) =>
                        set({ schedules: state.schedules.map((s) => s.id === w.id ? { ...s, end: e.target.value } : s) })
                      }
                      className="w-20 bg-muted/50 border border-border/50 rounded px-2 py-1 text-[11px] font-mono text-muted-foreground focus:outline-none"
                    />
                  </div>
                  <button
                    onClick={() => set({ schedules: state.schedules.filter((s) => s.id !== w.id) })}
                    className="text-muted-foreground/70 hover:text-muted-foreground text-[16px] transition-colors"
                  >
                    ×
                  </button>
                </div>
                <DayPills
                  selected={w.days}
                  onChange={(days) =>
                    set({ schedules: state.schedules.map((s) => s.id === w.id ? { ...s, days } : s) })
                  }
                />
              </div>
            ))}
            {state.schedules.length === 0 && (
              <div className="text-[11px] text-muted-foreground/70 text-center py-10">
                No schedule windows — always study mode
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Unlock ─────────────────────────────────────────────────────────────────

function UnlockSection({ state, set }: { state: AppState; set: (s: Partial<AppState>) => void }) {
  const [passPhrase, setPassPhrase] = useState("");
  const [rewardPhrase, setRewardPhrase] = useState("");
  const goalPct = Math.min(100, Math.round((state.productiveMinutes / state.goalMinutes) * 100));

  return (
    <div>
      <SectionHeader title="Unlock" description="Three doors to unlock the day." />

      <div className="grid grid-cols-3 gap-2 mb-5">
        {[
          { label: "Earn it", sub: "Goal + Bible chapter", met: goalPct >= 100 && state.chapterDone },
          { label: "Reward day", sub: `${state.rewardDays} available`, met: state.rewardDays > 0 },
          { label: "Day pass", sub: "2 per week", met: false },
        ].map(({ label, sub, met }) => (
          <div key={label} className={`border rounded-lg p-3 text-center ${met ? "bg-emerald-500/10 border-emerald-500/30" : "bg-muted/40 border-border/50"}`}>
            <div className="text-[10px] font-mono text-muted-foreground uppercase mb-1">{label}</div>
            <div className="text-[11px] text-muted-foreground">{sub}</div>
            {met && <div className="mt-1 text-[10px] font-mono text-emerald-600 dark:text-emerald-400">✓</div>}
          </div>
        ))}
      </div>

      <Card className="mb-4">
        <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase mb-3">Daily goal</div>
        <div className="flex items-center gap-3 mb-2">
          <input
            type="number" min={15} max={960} step={15}
            value={state.goalMinutes}
            onChange={(e) => set({ goalMinutes: Number(e.target.value) })}
            className="w-24 px-3 py-1.5 bg-background/50 border border-border/50 rounded text-[13px] font-mono text-foreground focus:outline-none focus:border-border/60"
          />
          <span className="text-[12px] text-muted-foreground">min</span>
          <span className="text-[11px] text-muted-foreground/50">({Math.round(state.goalMinutes / 60 * 10) / 10}h) — same as Plan "daily focus"</span>
        </div>
        <div className="w-full bg-muted rounded-full h-1 mb-1">
          <div className="bg-primary h-1 rounded-full transition-all" style={{ width: `${goalPct}%` }} />
        </div>
        <div className="flex justify-between">
          <span className="text-[10px] font-mono text-muted-foreground/70">{state.productiveMinutes} min productive</span>
          <span className="text-[10px] font-mono text-muted-foreground/70">{goalPct}%</span>
        </div>
      </Card>

      <Card className="mb-4">
        <SettingRow label="Bible chapter" description="Must be ticked by hand. Earns 15 min. Required for Earn-it door.">
          <Toggle checked={state.chapterDone} onChange={(v) => set({ chapterDone: v })} />
        </SettingRow>
      </Card>

      <Card className="mb-4">
        <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase mb-2">Reward day</div>
        <div className="text-[11px] text-muted-foreground mb-3 leading-relaxed">
          4 qualifying days (goal + Bible) = 1 reward day. Refused if today already unlocked — saves the credit. Ends at midnight.
        </div>
        <div className="flex gap-2">
          <input
            value={rewardPhrase} onChange={(e) => setRewardPhrase(e.target.value)}
            placeholder='Type "REWARD" to claim'
            className="flex-1 px-3 py-1.5 bg-background/50 border border-border/50 rounded text-[12px] font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-border/60"
          />
          <button
            disabled={rewardPhrase !== "REWARD" || state.rewardDays < 1}
            onClick={() => { set({ rewardDays: state.rewardDays - 1 }); setRewardPhrase(""); }}
            className="px-4 py-1.5 bg-muted hover:bg-accent/60 disabled:opacity-30 disabled:cursor-not-allowed border border-border/50 rounded text-[11px] text-muted-foreground transition-colors"
          >
            Claim
          </button>
        </div>
      </Card>

      <Card className="mb-4">
        <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase mb-2">Day pass</div>
        <div className="text-[11px] text-muted-foreground mb-1 leading-relaxed">
          2 per week. Buys the day, not the morning.
          <span className="ml-1 text-amber-700/70">Pass may not unlock sites until P5a.</span>
        </div>
        <div className="flex gap-2 mt-3">
          <input
            value={passPhrase} onChange={(e) => setPassPhrase(e.target.value)}
            placeholder='Type "PASS" to use'
            className="flex-1 px-3 py-1.5 bg-background/50 border border-border/50 rounded text-[12px] font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-border/60"
          />
          <button
            disabled={passPhrase !== "PASS"}
            onClick={() => setPassPhrase("")}
            className="px-4 py-1.5 bg-muted hover:bg-accent/60 disabled:opacity-30 disabled:cursor-not-allowed border border-border/50 rounded text-[11px] text-muted-foreground transition-colors"
          >
            Use
          </button>
        </div>
      </Card>

      <Card>
        <SettingRow label="Study Loop gate" description="Off by default. Forces morning into study mode until daily bite is done.">
          <Toggle checked={state.studyLoopGate} onChange={(v) => set({ studyLoopGate: v })} />
        </SettingRow>
      </Card>
    </div>
  );
}

// ── Productive ─────────────────────────────────────────────────────────────

function ProductiveSection({ state, set }: { state: AppState; set: (s: Partial<AppState>) => void }) {
  const cats = [
    { name: "Coding", score: 95 },
    { name: "Writing", score: 90 },
    { name: "Reading", score: 80 },
    { name: "Research", score: 75 },
    { name: "Meetings", score: 60 },
    { name: "Email", score: 50 },
    { name: "YouTube", score: 0 },
    { name: "Reddit", score: 0 },
  ];

  return (
    <div>
      <SectionHeader title="Productive" description="What counts toward your goal." badge={<NeedsApiBadge />} />

      <div className="p-3 bg-primary/10 border border-primary/20 rounded-lg mb-4 text-[10px] text-primary/80">
        All settings here go through Python API (:8000). With API down, scores freeze — blocking still runs.
      </div>

      <Card className="mb-4">
        <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase mb-3">Productive threshold</div>
        <div className="flex items-center gap-3 mb-1">
          <input
            type="range" min={0} max={100} value={state.threshold}
            onChange={(e) => set({ threshold: Number(e.target.value) })}
            className="flex-1"
          />
          <span className="w-8 text-right text-[12px] font-mono text-muted-foreground">{state.threshold}</span>
        </div>
        <div className="text-[10px] text-muted-foreground/70">Sessions scoring ≥ threshold count toward goal. Default 60.</div>
      </Card>

      <Card>
        <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase mb-3">Category scores</div>
        <div className="space-y-2">
          {cats.map(({ name, score }) => (
            <div key={name} className="flex items-center gap-3">
              <div className="w-20 text-[11px] font-mono text-muted-foreground">{name}</div>
              <div className="flex-1 bg-muted rounded-full h-1">
                <div
                  className={`h-1 rounded-full ${score >= 60 ? "bg-primary" : score > 0 ? "bg-amber-800" : "bg-muted"}`}
                  style={{ width: `${score}%` }}
                />
              </div>
              <div className="w-7 text-right text-[11px] font-mono text-muted-foreground/60">{score}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ── Tools ──────────────────────────────────────────────────────────────────

function WatchPage() {
  const [connected, setConnected] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const sessions = [
    { date: "2026-09-08", steps: 8420, activeMin: 34, hr: 72 },
    { date: "2026-09-07", steps: 11200, activeMin: 51, hr: 68 },
    { date: "2026-09-06", steps: 6800, activeMin: 22, hr: 74 },
  ];

  return (
    <div>
      <SectionHeader title="Watch sync" description="Sync wearable data with the productivity tracker." />

      <Card className="mb-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-[13px] font-medium text-foreground mb-1">Wearable connection</div>
            <div className="text-[11px] text-muted-foreground">
              {connected ? "Pixel Watch 2 · last sync 14:03" : "No device connected"}
            </div>
          </div>
          <div className={`w-2.5 h-2.5 rounded-full ${connected ? "bg-emerald-500" : "bg-muted"}`} />
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setConnected(!connected)}
            className="flex-1 py-2 bg-muted hover:bg-accent/60 border border-border/50 rounded text-[12px] text-muted-foreground transition-colors"
          >
            {connected ? "Disconnect" : "Connect device"}
          </button>
          <button
            disabled={!connected || syncing}
            onClick={() => { setSyncing(true); setTimeout(() => setSyncing(false), 1500); }}
            className="flex-1 py-2 bg-primary/15 hover:bg-primary/25 disabled:opacity-30 disabled:cursor-not-allowed border border-primary/30 rounded text-[12px] text-primary transition-colors"
          >
            {syncing ? "Syncing…" : "Sync now"}
          </button>
        </div>
      </Card>

      <Card className="mb-4">
        <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase mb-3">Recent sessions</div>
        <div className="space-y-0">
          {sessions.map((s) => (
            <div key={s.date} className="flex items-center gap-4 py-3 border-b border-border/40 last:border-0">
              <div className="text-[11px] font-mono text-muted-foreground w-24">{s.date}</div>
              <div className="flex-1 flex gap-6">
                <div>
                  <div className="text-[10px] text-muted-foreground/70 uppercase">Steps</div>
                  <div className="text-[12px] font-mono text-muted-foreground">{s.steps.toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground/70 uppercase">Active</div>
                  <div className="text-[12px] font-mono text-muted-foreground">{s.activeMin} min</div>
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground/70 uppercase">Avg HR</div>
                  <div className="text-[12px] font-mono text-muted-foreground">{s.hr} bpm</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase mb-3">Settings</div>
        <SettingRow label="Auto-sync on wake" description="Sync when Focus launches.">
          <Toggle checked={true} onChange={() => {}} />
        </SettingRow>
        <SettingRow label="Count active minutes toward goal" description="Wearable active minutes added to productive total.">
          <Toggle checked={false} onChange={() => {}} />
        </SettingRow>
      </Card>
    </div>
  );
}

function ExportPage() {
  const [range, setRange] = useState<"week" | "month" | "custom">("week");
  const [fmt, setFmt] = useState<"json" | "csv">("json");
  const [exporting, setExporting] = useState(false);

  const doExport = () => {
    setExporting(true);
    setTimeout(() => setExporting(false), 1200);
  };

  return (
    <div>
      <SectionHeader title="Export" description="Download your productivity and activity data." />

      <Card className="mb-4">
        <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase mb-3">Range</div>
        <div className="flex gap-1.5 mb-4">
          {(["week", "month", "custom"] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`flex-1 py-1.5 rounded text-[11px] capitalize border transition-colors ${
                range === r ? "bg-muted border-border/60 text-foreground" : "bg-background/50 border-border/50 text-muted-foreground hover:text-muted-foreground"
              }`}
            >
              {r === "week" ? "This week" : r === "month" ? "This month" : "Custom"}
            </button>
          ))}
        </div>
        {range === "custom" && (
          <div className="flex gap-2 mb-4">
            <input type="date" className="flex-1 bg-background/50 border border-border/50 rounded px-3 py-1.5 text-[11px] font-mono text-muted-foreground focus:outline-none" />
            <span className="text-muted-foreground/50 self-center">–</span>
            <input type="date" className="flex-1 bg-background/50 border border-border/50 rounded px-3 py-1.5 text-[11px] font-mono text-muted-foreground focus:outline-none" />
          </div>
        )}
        <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase mb-2">Format</div>
        <div className="flex gap-1.5 mb-4">
          {(["json", "csv"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFmt(f)}
              className={`px-4 py-1.5 rounded text-[11px] font-mono uppercase border transition-colors ${
                fmt === f ? "bg-muted border-border/60 text-foreground" : "bg-background/50 border-border/50 text-muted-foreground hover:text-muted-foreground"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
        <button
          onClick={doExport}
          disabled={exporting}
          className="w-full py-2 bg-primary/15 hover:bg-primary/25 disabled:opacity-50 border border-primary/30 rounded text-[12px] text-primary transition-colors"
        >
          {exporting ? "Exporting…" : "Export"}
        </button>
      </Card>

      <Card>
        <div className="text-[9px] font-mono text-muted-foreground tracking-widest uppercase mb-3">Includes</div>
        <div className="space-y-1.5 text-[11px] text-muted-foreground">
          {["Productive sessions (merged, sleep subtracted)", "Category scores per session", "Earned minutes ledger", "Reward day history", "Kill events log (enforcer_kills.log)"].map((item) => (
            <div key={item} className="flex items-start gap-2">
              <span className="text-muted-foreground/50 mt-0.5">·</span>
              <span>{item}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function OtherToolsPage() {
  return (
    <div>
      <SectionHeader title="Tools" description="Demo, reminders, and setup." />
      <div className="grid grid-cols-2 gap-3">
        {[
          { title: "Demo mode", desc: "Move the fake clock to test schedule changes without affecting your live day.", action: "Open demo clock" },
          { title: "Reminders", desc: "Browser notifications for plan blocks and incubation ends.", action: "Configure" },
          { title: "Gate extension", desc: "Install or update the Edge Gate browser extension.", action: "Setup docs" },
          { title: "Enforcer setup", desc: "Install calt_enforcer as a Windows service for stay-alive.", action: "Setup docs" },
          { title: "Msg host setup", desc: "Register calt_msg_host.exe for the Gate extension.", action: "Setup docs" },
          { title: "Diagnostic", desc: "Run status.snapshot and get_mode to verify the full stack.", action: "Run check" },
        ].map(({ title, desc, action }) => (
          <Card key={title} className="flex flex-col">
            <div className="text-[12px] font-medium text-foreground/80 mb-1">{title}</div>
            <div className="text-[11px] text-muted-foreground leading-relaxed flex-1">{desc}</div>
            <button className="mt-3 w-full py-1.5 bg-muted hover:bg-accent/60 border border-border/50 rounded text-[11px] text-muted-foreground transition-colors">
              {action}
            </button>
          </Card>
        ))}
      </div>
    </div>
  );
}

function ToolsSection() {
  const [tab, setTab] = useState<ToolTab>("watch");
  return (
    <div>
      <div className="flex gap-1 mb-6 rounded-xl border border-border/50 bg-background/35 p-1">
        {([
          { id: "watch" as ToolTab, label: "Watch sync" },
          { id: "export" as ToolTab, label: "Export" },
          { id: "other" as ToolTab, label: "Other" },
        ]).map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`flex-1 py-1.5 rounded-lg text-[11px] font-medium transition-colors ${
              tab === id ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "watch" && <WatchPage />}
      {tab === "export" && <ExportPage />}
      {tab === "other" && <OtherToolsPage />}
    </div>
  );
}

// ── nav + shell ────────────────────────────────────────────────────────────

const NAV: { id: Section; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "rules", label: "Rules" },
  { id: "unlock", label: "Unlock" },
  { id: "productive", label: "Productive" },
  { id: "tools", label: "Tools" },
];

const INITIAL_STATE: AppState = {
  softlandEnabled: true,
  armed: false,
  mode: "study",
  modeUntil: "17:30",
  earnedMinutes: 25,
  goalMinutes: 240,
  productiveMinutes: 142,
  chapterDone: false,
  rewardDays: 2,
  rules: [
    { id: "1", value: "meet.google.com", type: "site", list: "allow" },
    { id: "2", value: "classroom.google.com", type: "site", list: "allow" },
    { id: "3", value: "news.ycombinator.com", type: "site", list: "watch" },
    { id: "4", value: "Steam.exe", type: "app", list: "block" },
    { id: "5", value: "Discord.exe", type: "app", list: "block" },
  ],
  schedules: [
    { id: "1", days: [0, 1, 2, 3, 4], start: "09:00", end: "17:30", mode: "study" },
    { id: "2", days: [0, 1, 2, 3, 4], start: "21:00", end: "23:59", mode: "free" },
  ],
  blockPorn: true,
  blockWatchSites: true,
  lockMode: "none",
  studyLoopGate: false,
  threshold: 60,
};

type MakeSettingsAppProps = {
  section?: Section;
  onSectionChange?: (id: Section) => void;
};

export default function MakeSettingsApp({
  section: sectionProp,
  onSectionChange,
}: MakeSettingsAppProps) {
  const [sectionLocal, setSectionLocal] = useState<Section>("overview");
  const section = sectionProp ?? sectionLocal;
  const setSection = (id: Section) => {
    if (onSectionChange) onSectionChange(id);
    else setSectionLocal(id);
  };
  const [state, setState] = useState<AppState>(INITIAL_STATE);
  const set = (partial: Partial<AppState>) => setState((s) => ({ ...s, ...partial }));

  return (
    <div className="flex min-h-[70vh] h-full bg-background text-foreground overflow-hidden">
      <aside className="w-48 flex-shrink-0 flex flex-col border-r border-border/50 bg-card/40">
        <nav className="flex-1 overflow-y-auto p-3">
          <div className="flex flex-col gap-1 rounded-xl border border-border/50 bg-background/35 p-1">
            {NAV.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => setSection(id)}
                className={`w-full rounded-lg px-3 py-2 text-left text-[12px] font-medium transition-colors ${
                  section === id
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                }`}
              >
                {label}
                {id === "productive" && (
                  <span
                    className={`ml-1.5 text-[9px] font-mono ${
                      section === id ? "text-primary-foreground/70" : "text-primary/60"
                    }`}
                  >
                    API
                  </span>
                )}
              </button>
            ))}
          </div>
        </nav>

        <div className="px-4 py-3 border-t border-border/50">
          <div className="text-[8px] font-mono text-muted-foreground/60 tracking-widest uppercase mb-1">
            Mode
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                state.mode === "study"
                  ? "bg-amber-500"
                  : state.mode === "free"
                    ? "bg-emerald-500"
                    : "bg-rose-500"
              }`}
            />
            <span className="text-[10px] font-mono text-muted-foreground capitalize">{state.mode}</span>
            <span className="text-[9px] font-mono text-muted-foreground/60 ml-auto">{state.modeUntil}</span>
          </div>
        </div>
      </aside>

      <main className="flex-1 min-w-0 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-6 sm:px-8 py-6 sm:py-8">
          {section === "overview" && <OverviewSection state={state} set={set} />}
          {section === "rules" && <RulesSection state={state} set={set} />}
          {section === "unlock" && <UnlockSection state={state} set={set} />}
          {section === "productive" && <ProductiveSection state={state} set={set} />}
          {section === "tools" && <ToolsSection />}
        </div>
      </main>
    </div>
  );
}
