import { useCallback, useEffect, useState } from "react";
import { Globe, Plus, Save } from "lucide-react";
import {
  fetchSoftLandSiteRules,
  saveSoftLandSiteRules,
  type SoftLandSiteRules,
} from "../../api/behaviorClient";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";

type ListKey = "allow_extra" | "watch_extra" | "block_extra";

const LISTS: { key: ListKey; title: string; hint: string; chipClass: string }[] = [
  {
    key: "allow_extra",
    title: "Allow extra",
    hint: "Always allowed — wins over every block below, including the porn filter",
    chipClass: "border-emerald-400/30 bg-emerald-500/10",
  },
  {
    key: "watch_extra",
    title: "Watch extra",
    hint: "Blocked in study mode only — free mode, a free window or a reward day lets these through",
    chipClass: "border-amber-400/30 bg-amber-500/10",
  },
  {
    key: "block_extra",
    title: "Block extra",
    hint: "Blocked in every mode, even on a reward day (still does not Arm OS kills)",
    chipClass: "border-rose-400/30 bg-rose-500/10",
  },
];

function normalizeDomain(raw: string): string {
  let s = raw.trim().toLowerCase().replace(/^https?:\/\//, "");
  s = s.split("/")[0] || "";
  if (s.startsWith("www.")) s = s.slice(4);
  return s;
}

export function SoftLandSiteRulesPanel() {
  const [data, setData] = useState<SoftLandSiteRules | null>(null);
  const [drafts, setDrafts] = useState<Record<ListKey, string>>({
    allow_extra: "",
    watch_extra: "",
    block_extra: "",
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [via, setVia] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await fetchSoftLandSiteRules());
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load site rules");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const addDomain = (key: ListKey) => {
    if (!data) return;
    const host = normalizeDomain(drafts[key]);
    if (!host || !host.includes(".")) return;
    const cur = data[key] || [];
    if (cur.some((d) => d === host)) {
      setDrafts((d) => ({ ...d, [key]: "" }));
      return;
    }
    setData({ ...data, [key]: [...cur, host] });
    setDrafts((d) => ({ ...d, [key]: "" }));
    setSaved(false);
  };

  const removeDomain = (key: ListKey, host: string) => {
    if (!data) return;
    setData({ ...data, [key]: (data[key] || []).filter((d) => d !== host) });
    setSaved(false);
  };

  const save = async () => {
    if (!data) return;
    setSaving(true);
    setError(null);
    try {
      if (isFocusEnforcerBridgeAvailable()) {
        const res = await enforcerNativeCmd("softland.patch_site_rules", {
          allow_extra: data.allow_extra || [],
          watch_extra: data.watch_extra || [],
          block_extra: data.block_extra || [],
        });
        if (res?.ok) {
          setVia("enforcer gateway");
          setSaved(true);
          setTimeout(() => setSaved(false), 2500);
          return;
        }
      }
      setData(await saveSoftLandSiteRules(data));
      setVia("API");
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (!data) {
    return <p className="text-xs text-muted-foreground">Loading SoftLand site rules…</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-sm flex items-center gap-2">
            <Globe size={16} className="text-sky-300" />
            SoftLand site rules
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Persists to <code className="text-[10px]">softland_policy.json</code> (Phase 2 SoT). SoftLand ≠ Arm.
            {via ? <span className="ml-1 text-emerald-300">saved via {via}</span> : null}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/70 hover:bg-emerald-600 text-xs disabled:opacity-50"
        >
          <Save size={12} /> {saving ? "Saving…" : saved ? "Saved" : "Save"}
        </button>
      </div>

      {error ? <p className="text-xs text-rose-300">{error}</p> : null}

      <div className="space-y-4">
        {LISTS.map(({ key, title, hint, chipClass }) => (
          <div key={key} className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2">
            <div>
              <p className="text-xs font-medium">{title}</p>
              <p className="text-[11px] text-muted-foreground">{hint}</p>
            </div>
            <div className="flex flex-wrap gap-1.5 min-h-[1.25rem]">
              {(data[key] || []).length === 0 ? (
                <span className="text-[10px] text-muted-foreground">None</span>
              ) : (
                (data[key] || []).map((host) => (
                  <button
                    key={host}
                    type="button"
                    onClick={() => removeDomain(key, host)}
                    className={`text-[10px] px-2 py-0.5 rounded border ${chipClass}`}
                    title="Remove"
                  >
                    {host} ×
                  </button>
                ))
              )}
            </div>
            <div className="flex gap-2">
              <input
                value={drafts[key]}
                onChange={(e) => setDrafts((d) => ({ ...d, [key]: e.target.value }))}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addDomain(key);
                  }
                }}
                placeholder="example.com"
                className="flex-1 rounded border border-white/10 bg-black/30 px-2 py-1 text-xs"
              />
              <button
                type="button"
                onClick={() => addDomain(key)}
                className="inline-flex items-center gap-1 px-2 py-1 rounded border border-white/15 text-xs"
              >
                <Plus size={12} /> Add
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SoftLandSiteRulesPanel;
