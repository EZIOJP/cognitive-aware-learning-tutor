import { useCallback, useEffect, useMemo, useState } from "react";
import {
  type ClassificationSuggestion,
  approveClassification,
  editAndApproveClassification,
  fetchPendingClassifications,
  rejectClassification,
  scanClassifications,
} from "../../api/behaviorClient";
import { loadLlmPrefs } from "../../api/transcriptsClient";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import {
  FOCUS_CLASSIFY_CATEGORIES,
  loadFocusClassifyPending,
  markFocusClassifyStatus,
  scanFocusClassifications,
} from "../../lib/focusOpenJarvisBrain";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";

const CUSTOM_CATS_KEY = "calt:focus-classify-custom-cats:v1";
const NEW_CATEGORY_VALUE = "__new__";

function loadCustomCategories(): string[] {
  try {
    const raw = localStorage.getItem(CUSTOM_CATS_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw) as unknown;
    if (!Array.isArray(arr)) return [];
    return arr
      .map((x) => String(x || "").trim())
      .filter(Boolean)
      .slice(0, 40);
  } catch {
    return [];
  }
}

function rememberCustomCategory(name: string): string[] {
  const n = name.trim();
  if (!n) return loadCustomCategories();
  const next = [n, ...loadCustomCategories().filter((c) => c.toLowerCase() !== n.toLowerCase())].slice(
    0,
    40,
  );
  try {
    localStorage.setItem(CUSTOM_CATS_KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
  return next;
}

function focusItemsToSuggestions(): ClassificationSuggestion[] {
  return loadFocusClassifyPending()
    .items.filter((i) => i.status === "pending")
    .map((i, idx) => ({
      id: idx + 1 + Math.abs(hashStr(i.id)) % 100000,
      key: i.key,
      key_type: "app",
      suggested_category: i.suggested_category,
      confidence: Math.round(i.confidence * 100),
      sample_titles: [i.label],
      occurrence_count: Math.max(1, Math.round((i.seconds || 0) / 60)),
      status: "pending",
      reviewed_at: null,
      created_at: null,
    }));
}

function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return h;
}

function patternFromKey(key: string): string {
  let k = key.trim();
  if (k.startsWith("app:")) k = k.slice(4);
  // Escape regex metacharacters for classify_rules patterns.
  return k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function focusApproveByKey(key: string, category: string): Promise<number> {
  const item = loadFocusClassifyPending().items.find((i) => i.key === key);
  if (item) markFocusClassifyStatus(item.id, "approved", category);
  if (!isFocusEnforcerBridgeAvailable()) return 0;
  const pattern = patternFromKey(key);
  const r = await enforcerNativeCmd("classify.upsert_app_rule", {
    pattern,
    category,
    score: 50,
  });
  return r?.ok ? 1 : 0;
}

const CATEGORY_COLORS: Record<string, string> = {
  "IDE / Code Editor": "bg-sky-600",
  Terminal: "bg-gray-600",
  "Dev Tools": "bg-violet-600",
  "Coding Practice": "bg-sky-700",
  "Study / Reading": "bg-emerald-600",
  "Study (Browser)": "bg-emerald-700",
  "Coursework (Browser)": "bg-cyan-600",
  "AI Tools": "bg-violet-500",
  "AI / ML": "bg-violet-700",
  "AI Assistant": "bg-purple-600",
  Research: "bg-teal-700",
  Documentation: "bg-slate-500",
  "Knowledge Work": "bg-teal-600",
  "Office / Docs": "bg-blue-500",
  Design: "bg-pink-500",
  "File Manager": "bg-stone-500",
  Gaming: "bg-orange-500",
  "Video Streaming": "bg-red-500",
  "Video (YouTube)": "bg-red-600",
  "Music / Media": "bg-fuchsia-500",
  "Social Media": "bg-rose-500",
  Entertainment: "bg-orange-600",
  Shopping: "bg-yellow-700",
  Browser: "bg-indigo-500",
  Communication: "bg-amber-500",
  System: "bg-zinc-500",
  "System Tools": "bg-zinc-500",
  Other: "bg-neutral-400",
};

/** Built-in list + Focus brain list (deduped). Custom cats loaded at runtime. */
const BUILTIN_CATEGORIES = Array.from(
  new Set([...Object.keys(CATEGORY_COLORS), ...FOCUS_CLASSIFY_CATEGORIES]),
);

type Props = {
  trackerNoData?: boolean;
};

export default function ClassificationReview({ trackerNoData = false }: Props) {
  const [suggestions, setSuggestions] = useState<ClassificationSuggestion[]>([]);
  const [scanning, setScanning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [editCategory, setEditCategory] = useState("");
  const [creatingNew, setCreatingNew] = useState(false);
  const [customCats, setCustomCats] = useState<string[]>(() => loadCustomCategories());

  const focusShell = isFocusDesktopShell();

  const categoryChoices = useMemo(() => {
    const custom = customCats.filter(
      (c) => !BUILTIN_CATEGORIES.some((b) => b.toLowerCase() === c.toLowerCase()),
    );
    return [...BUILTIN_CATEGORIES.filter((c) => c !== "Other"), ...custom, "Other"];
  }, [customCats]);

  const loadPending = useCallback(async () => {
    try {
      setLoading(true);
      if (focusShell) {
        setSuggestions(focusItemsToSuggestions());
        setError(null);
      } else {
        const data = await fetchPendingClassifications();
        setSuggestions(data.suggestions);
        setError(null);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [focusShell]);

  useEffect(() => {
    loadPending();
  }, [loadPending]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const handleScan = async () => {
    try {
      setScanning(true);
      setError(null);
      if (focusShell) {
        const result = await scanFocusClassifications(16);
        if (result.error) {
          showToast(`OpenJarvis classify failed — ${result.error}. Keep jarvis serve on :8000.`);
        } else if (result.created === 0 && result.scanned > 0) {
          showToast(`Scanned ${result.scanned} — no new suggestions.`);
        } else {
          showToast(`OpenJarvis scanned ${result.scanned}, created ${result.created}`);
        }
        await loadPending();
        return;
      }
      const result = await scanClassifications(20, loadLlmPrefs());
      if (result.llm_error === "unreachable") {
        showToast(
          "LM Studio offline — start Local Server on port 1234 with google/gemma-4-e4b loaded, then retry.",
        );
      } else if (result.created === 0 && result.scanned > 0) {
        showToast(`Scanned ${result.scanned} keys — no new suggestions (rules/LLM had no match).`);
      } else {
        showToast(`Scanned ${result.scanned} keys, created ${result.created} suggestions`);
      }
      await loadPending();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  };

  const handleApprove = async (id: number) => {
    try {
      if (focusShell) {
        const row = suggestions.find((s) => s.id === id);
        if (!row) return;
        const n = await focusApproveByKey(row.key, row.suggested_category);
        setSuggestions((prev) => prev.filter((s) => s.id !== id));
        showToast(n ? `Rule saved for ${row.key}` : `Marked approved (enforcer write skipped)`);
        return;
      }
      const result = await approveClassification(id);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
      showToast(`Applied to ${result.affected_rows} past sessions`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Approve failed");
    }
  };

  const handleReject = async (id: number) => {
    try {
      if (focusShell) {
        const row = suggestions.find((s) => s.id === id);
        if (row) {
          const item = loadFocusClassifyPending().items.find((i) => i.key === row.key);
          if (item) markFocusClassifyStatus(item.id, "rejected");
        }
        setSuggestions((prev) => prev.filter((s) => s.id !== id));
        return;
      }
      await rejectClassification(id);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Reject failed");
    }
  };

  const resetEdit = () => {
    setEditId(null);
    setEditCategory("");
    setCreatingNew(false);
  };

  const handleEditApprove = async (id: number) => {
    const cat = editCategory.trim();
    if (!cat || cat === NEW_CATEGORY_VALUE) return;
    try {
      const isCustom = !BUILTIN_CATEGORIES.some((b) => b.toLowerCase() === cat.toLowerCase());
      if (isCustom) setCustomCats(rememberCustomCategory(cat));

      if (focusShell) {
        const row = suggestions.find((s) => s.id === id);
        if (!row) return;
        const n = await focusApproveByKey(row.key, cat);
        setSuggestions((prev) => prev.filter((s) => s.id !== id));
        resetEdit();
        showToast(n ? `Saved "${cat}" for ${row.key}` : `Marked approved`);
        return;
      }
      const result = await editAndApproveClassification(id, cat);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
      resetEdit();
      showToast(`Applied "${result.category}" to ${result.affected_rows} past sessions`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Edit-approve failed");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white/90">App Classification</h3>
        <button
          onClick={handleScan}
          disabled={scanning || (!focusShell && trackerNoData)}
          className="rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
          title={
            focusShell
              ? "Scan via local OpenJarvis"
              : trackerNoData
                ? "Start the desktop tracker first"
                : undefined
          }
        >
          {scanning ? "Scanning…" : focusShell ? "Scan with OpenJarvis" : "Scan Uncategorized"}
        </button>
      </div>

      {focusShell ? (
        <p className="text-sm text-white/50">
          Local OpenJarvis classifies uncategorized apps from today&apos;s activity. Approve writes
          into <code className="text-[10px]">classify_rules.json</code>. SoftLand/Arm stay native.
        </p>
      ) : null}

      {!focusShell && trackerNoData && (
        <p className="text-sm text-white/50">
          No tracker data yet. Start the desktop tracker, use a few apps, then scan for uncategorized sessions.
        </p>
      )}

      {toast && (
        <div className="rounded-lg bg-emerald-900/60 border border-emerald-600/40 px-4 py-2 text-sm text-emerald-200">
          {toast}
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-red-900/40 border border-red-600/40 px-4 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-white/50">Loading…</p>
      ) : suggestions.length === 0 ? (
        <p className="text-sm text-white/50">
          No pending suggestions. Click "Scan Uncategorized" to find apps labelled "Other".
        </p>
      ) : (
        <div className="space-y-2">
          {suggestions.map((s) => (
            <div
              key={s.id}
              className="rounded-xl bg-white/5 border border-white/10 p-4 space-y-2"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm font-semibold text-white/90">
                  {s.key}
                </span>
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] uppercase text-white/50">
                  {s.key_type}
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs text-white ${CATEGORY_COLORS[s.suggested_category] ?? "bg-neutral-500"}`}
                >
                  {s.suggested_category}
                </span>
                <span className="text-xs text-white/40">
                  {s.confidence}% conf
                </span>
                <span className="text-xs text-white/40 ml-auto">
                  Would fix <span className="font-semibold text-white/70">{s.occurrence_count}</span> sessions
                </span>
              </div>

              {s.sample_titles.length > 0 && (
                <div className="text-xs text-white/40 truncate">
                  {s.sample_titles.slice(0, 2).join(" · ")}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2 pt-1">
                <button
                  onClick={() => handleApprove(s.id)}
                  className="rounded-lg bg-emerald-700/70 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-600 transition-colors"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleReject(s.id)}
                  className="rounded-lg bg-red-800/60 px-3 py-1 text-xs font-medium text-white hover:bg-red-700 transition-colors"
                >
                  Reject
                </button>
                {editId === s.id ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    {creatingNew ? (
                      <input
                        autoFocus
                        type="text"
                        value={editCategory === NEW_CATEGORY_VALUE ? "" : editCategory}
                        onChange={(e) => setEditCategory(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") void handleEditApprove(s.id);
                          if (e.key === "Escape") resetEdit();
                        }}
                        placeholder="New category name…"
                        aria-label="New category name"
                        maxLength={48}
                        className="min-w-[10rem] rounded-md border border-amber-500/40 bg-zinc-900 px-2 py-1 text-xs text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-amber-400"
                      />
                    ) : (
                      <select
                        value={editCategory}
                        onChange={(e) => {
                          const v = e.target.value;
                          if (v === NEW_CATEGORY_VALUE) {
                            setCreatingNew(true);
                            setEditCategory("");
                            return;
                          }
                          setCreatingNew(false);
                          setEditCategory(v);
                        }}
                        aria-label="Select category"
                        // Windows WebView paints native <option> with system colors;
                        // color-scheme:dark keeps text readable on the popup list.
                        style={{ colorScheme: "dark" }}
                        className="max-w-[14rem] rounded-md border border-white/20 bg-zinc-900 px-2 py-1 text-xs text-zinc-100 [color-scheme:dark]"
                      >
                        <option value="">Pick category…</option>
                        {categoryChoices.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                        {!categoryChoices.includes(editCategory) && editCategory ? (
                          <option value={editCategory}>{editCategory}</option>
                        ) : null}
                        <option value={NEW_CATEGORY_VALUE}>+ Create new category…</option>
                      </select>
                    )}
                    <button
                      onClick={() => void handleEditApprove(s.id)}
                      disabled={!editCategory.trim() || editCategory === NEW_CATEGORY_VALUE}
                      className="rounded bg-amber-700/70 px-2 py-1 text-xs text-white hover:bg-amber-600 disabled:opacity-40 transition-colors"
                    >
                      Save
                    </button>
                    {creatingNew ? (
                      <button
                        type="button"
                        onClick={() => {
                          setCreatingNew(false);
                          setEditCategory(s.suggested_category || "");
                        }}
                        className="rounded bg-white/10 px-2 py-1 text-xs text-white/60 hover:bg-white/20 transition-colors"
                      >
                        List
                      </button>
                    ) : null}
                    <button
                      type="button"
                      onClick={resetEdit}
                      className="rounded bg-white/10 px-2 py-1 text-xs text-white/60 hover:bg-white/20 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => {
                      setEditId(s.id);
                      setCreatingNew(false);
                      setEditCategory(s.suggested_category);
                      setCustomCats(loadCustomCategories());
                    }}
                    className="rounded-lg bg-white/10 px-3 py-1 text-xs text-white/60 hover:bg-white/20 transition-colors"
                  >
                    Edit & Approve
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
