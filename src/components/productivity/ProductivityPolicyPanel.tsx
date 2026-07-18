import { useCallback, useEffect, useState } from "react";
import { Loader2, Shield, Save } from "lucide-react";
import {
  fetchCategoryScores,
  fetchDistractionGate,
  fetchProductivityPolicy,
  saveCategoryScores,
  saveProductivityPolicy,
  type DistractionGate,
  type ProductivityPolicy,
} from "../../api/behaviorClient";

const COMMON_CATEGORIES = [
  "IDE / Code Editor",
  "Terminal",
  "Dev Tools",
  "Coding Practice",
  "Study / Reading",
  "Study (Browser)",
  "Coursework (Browser)",
  "AI Tools",
  "AI / ML",
  "Research",
  "Documentation",
  "Knowledge Work",
  "Office / Docs",
  "Gaming",
  "Video Streaming",
  "Music / Media",
  "Social Media",
  "Entertainment",
  "Shopping",
  "Browser",
  "Communication",
  "Other",
];

function fmtRemainMinutes(m: number): string {
  const n = Math.max(0, Math.round(m));
  if (n < 60) return `${n} min`;
  const h = Math.floor(n / 60);
  const rem = n % 60;
  return rem ? `${h}h ${rem}m` : `${h}h`;
}

type Props = {
  onSaved?: () => void;
};

export function ProductivityPolicyPanel({ onSaved }: Props) {
  const [policy, setPolicy] = useState<ProductivityPolicy | null>(null);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [gate, setGate] = useState<DistractionGate | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [overrideKey, setOverrideKey] = useState("");
  const [overrideCat, setOverrideCat] = useState("Study / Reading");
  const [newBlockExe, setNewBlockExe] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, s, g] = await Promise.all([
        fetchProductivityPolicy(),
        fetchCategoryScores(),
        fetchDistractionGate().catch(() => null),
      ]);
      setPolicy({
        ...p,
        hard_block_enabled: p.hard_block_enabled ?? false,
        daily_goal_minutes: p.daily_goal_minutes ?? 240,
        hard_block_gaming: p.hard_block_gaming ?? true,
        hard_block_exes: p.hard_block_exes ?? [],
      });
      setScores(s.scores || {});
      setGate(g);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load policy");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleList = (list: "productive_categories" | "blocked_categories", cat: string) => {
    if (!policy) return;
    const cur = new Set(policy[list]);
    if (cur.has(cat)) cur.delete(cat);
    else cur.add(cat);
    const next = { ...policy, [list]: [...cur].sort() };
    // Mutual exclusivity
    if (list === "productive_categories" && cur.has(cat)) {
      next.blocked_categories = next.blocked_categories.filter((c) => c !== cat);
    }
    if (list === "blocked_categories" && cur.has(cat)) {
      next.productive_categories = next.productive_categories.filter((c) => c !== cat);
    }
    setPolicy(next);
  };

  const save = async () => {
    if (!policy) return;
    setSaving(true);
    setError(null);
    setHint(null);
    try {
      const saved = await saveProductivityPolicy(policy);
      setPolicy(saved);
      await saveCategoryScores(scores);
      const g = await fetchDistractionGate().catch(() => null);
      setGate(g);
      setHint("Policy saved — tracker picks up hard-block within ~30s.");
      onSaved?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const addOverride = () => {
    if (!policy || !overrideKey.trim()) return;
    setPolicy({
      ...policy,
      app_overrides: {
        ...policy.app_overrides,
        [overrideKey.trim()]: overrideCat,
      },
    });
    setOverrideKey("");
  };

  if (loading) {
    return (
      <div className="gloss-panel rounded-xl p-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 size={14} className="animate-spin" /> Loading productivity policy…
      </div>
    );
  }

  if (!policy) {
    return (
      <div className="gloss-panel rounded-xl p-4 text-sm text-rose-300">
        {error || "No policy"}
      </div>
    );
  }

  const allCats = Array.from(
    new Set([...COMMON_CATEGORIES, ...Object.keys(scores), ...policy.productive_categories, ...policy.blocked_categories]),
  ).sort();

  return (
    <div className="gloss-panel rounded-xl p-4 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Shield size={14} className="text-violet-300" />
            Productivity policy
          </h3>
          <p className="text-xs text-muted-foreground mt-1 max-w-xl">
            Tuned for AI/ML (Scaler) deep work. Blocked categories never count as productive — even during a
            planned block. Override apps or single sessions for edge cases.
          </p>
        </div>
        <button
          type="button"
          disabled={saving}
          onClick={() => void save()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600/80 hover:bg-violet-600 text-xs disabled:opacity-50"
        >
          {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
          Save
        </button>
      </div>

      {error && <p className="text-xs text-rose-300">{error}</p>}
      {hint && <p className="text-xs text-emerald-300">{hint}</p>}

      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-xs font-semibold text-amber-100">Hard-block until daily goal</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Desktop tracker kills games (and custom exes) until today’s productive minutes hit the
              goal. Use Cold Turkey for YouTube/Netflix sites — don’t add chrome.exe here.
            </p>
          </div>
          <label className="flex items-center gap-2 text-xs shrink-0">
            <input
              type="checkbox"
              checked={Boolean(policy.hard_block_enabled)}
              onChange={(e) => setPolicy({ ...policy, hard_block_enabled: e.target.checked })}
            />
            Enabled
          </label>
        </div>
        {gate && (
          <div className="rounded-md border border-white/10 bg-black/30 p-2.5 flex gap-3 items-center">
            <div className="relative w-14 h-14 shrink-0">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 56 56" aria-hidden>
                <circle
                  cx="28"
                  cy="28"
                  r="22"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="5"
                  className="text-muted/30"
                />
                <circle
                  cx="28"
                  cy="28"
                  r="22"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="5"
                  strokeLinecap="round"
                  className={
                    gate.locked ? "text-amber-400" : gate.enabled ? "text-teal-400" : "text-muted-foreground"
                  }
                  strokeDasharray={`${2 * Math.PI * 22}`}
                  strokeDashoffset={`${
                    2 *
                    Math.PI *
                    22 *
                    (1 -
                      Math.min(
                        1,
                        gate.daily_goal_minutes > 0
                          ? gate.productive_minutes / gate.daily_goal_minutes
                          : 0,
                      ))
                  }`}
                />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold tabular-nums">
                {gate.daily_goal_minutes > 0
                  ? Math.min(
                      100,
                      Math.round((gate.productive_minutes / gate.daily_goal_minutes) * 100),
                    )
                  : 0}
                %
              </span>
            </div>
            <div className="min-w-0 flex-1 space-y-0.5">
              <p className="text-xs font-medium text-foreground/95">
                {gate.locked
                  ? "Games locked — work first"
                  : gate.enabled
                    ? "Unlocked for the rest of today"
                    : "Hard-block is off"}
              </p>
              <p className="text-[11px] text-muted-foreground">
                {gate.productive_minutes} / {gate.daily_goal_minutes} productive min
                {gate.locked ? ` · ${fmtRemainMinutes(gate.remaining_minutes)} left to unlock` : ""}
              </p>
              <div className="h-1.5 rounded-full bg-muted/30 overflow-hidden mt-1">
                <div
                  className={`h-full rounded-full ${gate.locked ? "bg-amber-400" : "bg-teal-400"}`}
                  style={{
                    width: `${Math.min(
                      100,
                      gate.daily_goal_minutes > 0
                        ? (gate.productive_minutes / gate.daily_goal_minutes) * 100
                        : 0,
                    )}%`,
                  }}
                />
              </div>
            </div>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <label className="flex items-center gap-2">
            Daily goal (min)
            <input
              type="number"
              min={15}
              max={960}
              value={policy.daily_goal_minutes ?? 240}
              onChange={(e) =>
                setPolicy({ ...policy, daily_goal_minutes: Number(e.target.value) || 240 })
              }
              className="w-20 rounded border border-white/10 bg-black/30 px-2 py-1"
            />
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={policy.hard_block_gaming !== false}
              onChange={(e) => setPolicy({ ...policy, hard_block_gaming: e.target.checked })}
            />
            Auto-block Gaming category
          </label>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
            Custom blocked exes
          </p>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {(policy.hard_block_exes || []).map((exe) => (
              <button
                key={exe}
                type="button"
                className="text-[10px] px-2 py-0.5 rounded border border-white/10 hover:border-rose-400/50"
                onClick={() =>
                  setPolicy({
                    ...policy,
                    hard_block_exes: (policy.hard_block_exes || []).filter((x) => x !== exe),
                  })
                }
                title="Remove"
              >
                {exe} ×
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              value={newBlockExe}
              onChange={(e) => setNewBlockExe(e.target.value)}
              placeholder="e.g. discord.exe"
              className="flex-1 rounded border border-white/10 bg-black/30 px-2 py-1 text-xs"
            />
            <button
              type="button"
              className="px-2 py-1 rounded border border-white/15 text-xs"
              onClick={() => {
                const name = newBlockExe.trim();
                if (!name || !policy) return;
                const cur = policy.hard_block_exes || [];
                if (cur.some((x) => x.toLowerCase() === name.toLowerCase())) {
                  setNewBlockExe("");
                  return;
                }
                setPolicy({ ...policy, hard_block_exes: [...cur, name] });
                setNewBlockExe("");
              }}
            >
              Add
            </button>
          </div>
        </div>
      </div>

      <label className="flex items-center gap-2 text-xs">
        Productive threshold
        <input
          type="number"
          min={1}
          max={100}
          value={policy.threshold}
          onChange={(e) => setPolicy({ ...policy, threshold: Number(e.target.value) || 60 })}
          className="w-16 rounded border border-white/10 bg-black/30 px-2 py-1"
        />
      </label>

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-emerald-300/80 mb-2">Counts as productive</p>
          <div className="max-h-48 overflow-y-auto space-y-1 pr-1">
            {allCats.map((cat) => {
              const on = policy.productive_categories.includes(cat);
              return (
                <label key={`p-${cat}`} className="flex items-center gap-2 text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => toggleList("productive_categories", cat)}
                  />
                  <span className={on ? "text-emerald-100" : "text-muted-foreground"}>{cat}</span>
                </label>
              );
            })}
          </div>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-rose-300/80 mb-2">Blocked (never productive)</p>
          <div className="max-h-48 overflow-y-auto space-y-1 pr-1">
            {allCats.map((cat) => {
              const on = policy.blocked_categories.includes(cat);
              return (
                <label key={`b-${cat}`} className="flex items-center gap-2 text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => toggleList("blocked_categories", cat)}
                  />
                  <span className={on ? "text-rose-100" : "text-muted-foreground"}>{cat}</span>
                </label>
              );
            })}
          </div>
        </div>
      </div>

      <div>
        <p className="text-[10px] uppercase tracking-wider text-sky-300/80 mb-2">Category scores (0–100)</p>
        <div className="grid sm:grid-cols-2 gap-2 max-h-40 overflow-y-auto">
          {allCats.slice(0, 24).map((cat) => (
            <label key={`s-${cat}`} className="flex items-center justify-between gap-2 text-[11px]">
              <span className="truncate text-muted-foreground">{cat}</span>
              <input
                type="number"
                min={0}
                max={100}
                value={scores[cat] ?? 35}
                onChange={(e) =>
                  setScores({ ...scores, [cat]: Math.max(0, Math.min(100, Number(e.target.value) || 0)) })
                }
                className="w-14 rounded border border-white/10 bg-black/30 px-1.5 py-0.5"
              />
            </label>
          ))}
        </div>
      </div>

      <div>
        <p className="text-[10px] uppercase tracking-wider text-violet-300/80 mb-2">App overrides (exe / domain → category)</p>
        <div className="flex flex-wrap gap-2 mb-2">
          <input
            value={overrideKey}
            onChange={(e) => setOverrideKey(e.target.value)}
            placeholder="steam.exe or scaler.com"
            className="flex-1 min-w-[140px] rounded border border-white/10 bg-black/30 px-2 py-1 text-xs"
          />
          <select
            value={overrideCat}
            onChange={(e) => setOverrideCat(e.target.value)}
            className="rounded border border-white/10 bg-black/30 px-2 py-1 text-xs"
          >
            {allCats.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={addOverride}
            className="px-2 py-1 rounded border border-white/15 text-xs hover:bg-white/5"
          >
            Add
          </button>
        </div>
        <ul className="space-y-1 text-xs">
          {Object.entries(policy.app_overrides).map(([key, cat]) => (
            <li key={key} className="flex items-center justify-between gap-2 rounded border border-white/5 px-2 py-1">
              <span>
                <span className="text-sky-200">{key}</span>
                <span className="text-muted-foreground"> → {cat}</span>
              </span>
              <button
                type="button"
                className="text-rose-300/80 hover:text-rose-200"
                onClick={() => {
                  const next = { ...policy.app_overrides };
                  delete next[key];
                  setPolicy({ ...policy, app_overrides: next });
                }}
              >
                Remove
              </button>
            </li>
          ))}
          {Object.keys(policy.app_overrides).length === 0 && (
            <li className="text-muted-foreground text-[11px]">No app overrides yet.</li>
          )}
        </ul>
      </div>
    </div>
  );
}

export default ProductivityPolicyPanel;
