import { useCallback, useEffect, useMemo, useState, type MutableRefObject } from "react";
import { Plus, Save } from "lucide-react";
import {
  fetchSoftLandSiteRules,
  saveSoftLandSiteRules,
  type SoftLandSiteRules,
} from "../../api/behaviorClient";
import { useFocusStatus, useFreeDay } from "../../hooks/useFocusStatus";
import { softlandSurgeryOpen } from "../../lib/dayGate";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { focusDataUrl } from "../../utils/focusDataUrl";
import { cn } from "../../app/components/ui/utils";

const EMPTY_RULES: SoftLandSiteRules = {
  allow_extra: [],
  watch_extra: [],
  block_extra: [],
};

type ListKey = "allow_extra" | "watch_extra" | "block_extra";
type SiteTag = "allow" | "focus" | "always";

const TAG_TO_KEY: Record<SiteTag, ListKey> = {
  allow: "allow_extra",
  focus: "watch_extra",
  always: "block_extra",
};

const KEY_TO_TAG: Record<ListKey, SiteTag> = {
  allow_extra: "allow",
  watch_extra: "focus",
  block_extra: "always",
};

const TAG_META: Record<
  SiteTag,
  { label: string; hint: string; chipClass: string }
> = {
  allow: {
    label: "Allow",
    hint: "Always open",
    chipClass: "border-emerald-400/30 bg-emerald-500/10 text-emerald-200/90",
  },
  focus: {
    label: "Focus",
    hint: "Blocked in study; open in free/reward",
    chipClass: "border-amber-400/30 bg-amber-500/10 text-amber-200/90",
  },
  always: {
    label: "Always",
    hint: "Blocked in every mode",
    chipClass: "border-rose-400/30 bg-rose-500/10 text-rose-200/90",
  },
};

const LISTS_SOFTLAND: { key: ListKey; title: string; hint: string; chipClass: string }[] = [
  {
    key: "allow_extra",
    title: "Allow",
    hint: "Always open. Beats every site rule.",
    chipClass: "border-emerald-400/30 bg-emerald-500/10",
  },
  {
    key: "watch_extra",
    title: "Watch",
    hint: "Closed while studying. Open when free.",
    chipClass: "border-amber-400/30 bg-amber-500/10",
  },
  {
    key: "block_extra",
    title: "Block",
    hint: "Closed in every mode, even reward days.",
    chipClass: "border-rose-400/30 bg-rose-500/10",
  },
];

/** Keep this sentence verbatim near every list editor. */
export const SOFTLAND_LADDER_ONE_LINER =
  "Allow always wins. Watch is study-only. Block stays after you unlock.";

function asStringList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.map((x) => String(x || "").trim().toLowerCase()).filter(Boolean);
}

async function loadSiteRules(): Promise<SoftLandSiteRules> {
  if (isFocusDesktopShell()) {
    const r = await fetch(focusDataUrl("softland_policy.json"), { cache: "no-store" });
    if (!r.ok) {
      throw new Error(
        `SoftLand mirror unavailable (${r.status}) — start calt_enforcer / Focus shell`,
      );
    }
    const j = (await r.json()) as {
      site_rules?: Partial<SoftLandSiteRules>;
      allow_extra?: string[];
      watch_extra?: string[];
      block_extra?: string[];
    };
    const sr = j.site_rules || j;
    return {
      allow_extra: asStringList(sr.allow_extra),
      watch_extra: asStringList(sr.watch_extra),
      block_extra: asStringList(sr.block_extra),
    };
  }
  return fetchSoftLandSiteRules();
}

function normalizeDomain(raw: string): string {
  let s = raw.trim().toLowerCase().replace(/^https?:\/\//, "");
  s = s.split("/")[0] || "";
  if (s.startsWith("www.")) s = s.slice(4);
  return s;
}

type SoftLandSiteRulesPanelProps = {
  mode?: "softland" | "blocker";
  /** When true, hide the save button (parent owns Save). */
  hideSave?: boolean;
  saveRef?: MutableRefObject<(() => Promise<void>) | null>;
};

type FlatRow = { host: string; tag: SiteTag };

export function SoftLandSiteRulesPanel({
  mode = "softland",
  hideSave = false,
  saveRef,
}: SoftLandSiteRulesPanelProps) {
  const freeDay = useFreeDay();
  const status = useFocusStatus();
  const canEditLists = softlandSurgeryOpen(status, freeDay);
  const [data, setData] = useState<SoftLandSiteRules | null>(null);
  const [drafts, setDrafts] = useState<Record<ListKey, string>>({
    allow_extra: "",
    watch_extra: "",
    block_extra: "",
  });
  const [unifiedDraft, setUnifiedDraft] = useState("");
  const [unifiedTag, setUnifiedTag] = useState<SiteTag>("focus");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [via, setVia] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await loadSiteRules());
      setError(null);
    } catch (e: unknown) {
      if (isFocusDesktopShell()) {
        setData(EMPTY_RULES);
        setError(
          e instanceof Error
            ? e.message
            : "Could not load SoftLand lists — start calt_enforcer or check /calt-data/softland_policy.json",
        );
        return;
      }
      setError(e instanceof Error ? e.message : "Failed to load site rules");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const flatRows: FlatRow[] = useMemo(() => {
    if (!data) return [];
    const rows: FlatRow[] = [];
    for (const key of ["allow_extra", "watch_extra", "block_extra"] as ListKey[]) {
      for (const host of data[key] || []) {
        rows.push({ host, tag: KEY_TO_TAG[key] });
      }
    }
    rows.sort((a, b) => a.host.localeCompare(b.host));
    return rows;
  }, [data]);

  const addDomain = (key: ListKey, raw: string) => {
    if (!data) return;
    const host = normalizeDomain(raw);
    if (!host || !host.includes(".")) return;
    // Drop from every list so a domain has one tag
    const next: SoftLandSiteRules = {
      allow_extra: (data.allow_extra || []).filter((d) => d !== host),
      watch_extra: (data.watch_extra || []).filter((d) => d !== host),
      block_extra: (data.block_extra || []).filter((d) => d !== host),
    };
    next[key] = [...(next[key] || []), host];
    setData(next);
    setSaved(false);
  };

  const removeDomain = (host: string) => {
    if (!data) return;
    setData({
      allow_extra: (data.allow_extra || []).filter((d) => d !== host),
      watch_extra: (data.watch_extra || []).filter((d) => d !== host),
      block_extra: (data.block_extra || []).filter((d) => d !== host),
    });
    setSaved(false);
  };

  const setRowTag = (host: string, tag: SiteTag) => {
    addDomain(TAG_TO_KEY[tag], host);
  };

  const save = useCallback(async () => {
    if (!data || !canEditLists) {
      if (!canEditLists) {
        setError(
          "Finish morning Bible" +
            (status.dayLoop?.planning_enabled ? " + Confirm plan" : "") +
            ", or use a free day / day pass.",
        );
      }
      return;
    }
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
        throw new Error("Enforcer gateway rejected SoftLand site rules");
      }
      if (isFocusDesktopShell()) {
        throw new Error(
          "SoftLand saves need calt_focus.exe (enforcer pipe). Design host :5180 is read-only for lists.",
        );
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
  }, [data, canEditLists, status.dayLoop?.planning_enabled]);

  useEffect(() => {
    if (saveRef) saveRef.current = () => save();
    return () => {
      if (saveRef) saveRef.current = null;
    };
  }, [save, saveRef]);

  if (!data) {
    return (
      <p className="text-xs text-muted-foreground">
        {mode === "blocker" ? "Loading website lists…" : "Loading SoftLand site rules…"}
      </p>
    );
  }

  if (mode === "blocker") {
    return (
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={unifiedDraft}
            onChange={(e) => setUnifiedDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addDomain(TAG_TO_KEY[unifiedTag], unifiedDraft);
                setUnifiedDraft("");
              }
            }}
            placeholder="example.com"
            className="min-w-[8rem] flex-1 rounded-lg border border-white/10 bg-black/30 px-2 py-1 text-[11px]"
          />
          <select
            value={unifiedTag}
            onChange={(e) => setUnifiedTag(e.target.value as SiteTag)}
            className="rounded-lg border border-white/10 bg-black/30 px-1.5 py-1 text-[11px] text-foreground"
            title={TAG_META[unifiedTag].hint}
          >
            {(Object.keys(TAG_META) as SiteTag[]).map((t) => (
              <option key={t} value={t}>
                {TAG_META[t].label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => {
              addDomain(TAG_TO_KEY[unifiedTag], unifiedDraft);
              setUnifiedDraft("");
            }}
            className="inline-flex items-center gap-1 rounded-lg border border-white/15 px-2 py-1 text-[11px]"
          >
            <Plus size={11} /> Add
          </button>
          {!hideSave ? (
            <button
              type="button"
              onClick={() => void save()}
              disabled={saving || !canEditLists}
              className="inline-flex items-center gap-1 rounded-lg bg-emerald-600/70 px-2 py-1 text-[11px] disabled:opacity-50"
            >
              <Save size={11} /> {saving ? "…" : saved ? "Saved" : "Save"}
            </button>
          ) : null}
        </div>

        {error ? <p className="text-[11px] text-rose-300">{error}</p> : null}
        {via && saved ? <p className="text-[10px] text-emerald-300">Saved via {via}</p> : null}

        <div className="flex flex-wrap gap-1 min-h-[1.5rem]">
          {flatRows.length === 0 ? (
            <span className="text-[10px] text-muted-foreground">No sites yet — add one above</span>
          ) : (
            flatRows.map(({ host, tag }) => (
              <div
                key={`${tag}-${host}`}
                className={cn(
                  "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px]",
                  TAG_META[tag].chipClass,
                )}
              >
                <select
                  value={tag}
                  onChange={(e) => setRowTag(host, e.target.value as SiteTag)}
                  className="bg-transparent border-0 text-[10px] font-medium focus:outline-none cursor-pointer max-w-[4.5rem]"
                  title={TAG_META[tag].hint}
                >
                  {(Object.keys(TAG_META) as SiteTag[]).map((t) => (
                    <option key={t} value={t} className="bg-zinc-900 text-foreground">
                      {TAG_META[t].label}
                    </option>
                  ))}
                </select>
                <span className="font-mono">{host}</span>
                <button
                  type="button"
                  onClick={() => removeDomain(host)}
                  className="opacity-60 hover:opacity-100 px-0.5"
                  title="Remove"
                >
                  ×
                </button>
              </div>
            ))
          )}
        </div>

        <p className="text-[10px] text-muted-foreground leading-snug">
          <span className="text-emerald-400/80">Allow</span> always ·{" "}
          <span className="text-amber-400/80">Focus</span> study-only ·{" "}
          <span className="text-rose-400/80">Always</span> every mode
        </p>
      </div>
    );
  }

  // SoftLand (Settings) — three buckets
  return (
    <div className="space-y-4">
      {error ? <p className="text-xs text-rose-300">{error}</p> : null}
      {via && saved ? <p className="text-[11px] text-emerald-300">Saved via {via}</p> : null}

      <div className="grid gap-3 md:grid-cols-3">
        {LISTS_SOFTLAND.map(({ key, title, hint, chipClass }) => (
          <div key={key} className="rounded-xl border border-border/40 bg-background/30 p-3 space-y-2">
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
                    onClick={() => removeDomain(host)}
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
                    addDomain(key, drafts[key]);
                    setDrafts((d) => ({ ...d, [key]: "" }));
                  }
                }}
                placeholder="add domain"
                aria-label={`Add ${title} domain`}
                className="min-h-11 flex-1 rounded-lg border border-border/50 bg-background px-3 text-[13px]"
              />
              <button
                type="button"
                onClick={() => {
                  addDomain(key, drafts[key]);
                  setDrafts((d) => ({ ...d, [key]: "" }));
                }}
                className="min-h-11 inline-flex items-center gap-1 rounded-lg border border-border/50 px-3 text-[13px]"
              >
                <Plus size={12} /> Add
              </button>
            </div>
          </div>
        ))}
      </div>

      <p className="text-[12px] text-muted-foreground leading-relaxed">
        The built-in watch list (YouTube, Reddit, X, Instagram and 11 more) cannot be edited. Put a
        site in Allow to open it.
        {!canEditLists
          ? " Finish morning Bible (and Confirm plan if Planning is on), or claim a free day / pass, to edit lists."
          : ""}
      </p>

      {!hideSave ? (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => void save()}
            disabled={saving || !canEditLists}
            className="min-h-11 inline-flex items-center gap-1.5 rounded-lg border border-[#0B6B63] bg-[#0B6B63] px-5 text-[13px] font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            <Save size={14} /> {saving ? "Saving…" : saved ? "Saved" : "Save site rules"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default SoftLandSiteRulesPanel;
