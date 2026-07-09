import { useCallback, useEffect, useState } from "react";
import {
  type ClassificationSuggestion,
  approveClassification,
  editAndApproveClassification,
  fetchPendingClassifications,
  rejectClassification,
  scanClassifications,
} from "../../api/behaviorClient";
import { loadLlmPrefs } from "../../api/transcriptsClient";

const CATEGORY_COLORS: Record<string, string> = {
  "IDE / Code Editor": "bg-sky-600",
  Terminal: "bg-gray-600",
  "Dev Tools": "bg-violet-600",
  "Study / Reading": "bg-emerald-600",
  "Knowledge Work": "bg-teal-600",
  "Office / Docs": "bg-blue-500",
  Design: "bg-pink-500",
  Communication: "bg-amber-500",
  Browser: "bg-indigo-500",
  "Coursework (Browser)": "bg-cyan-600",
  "File Manager": "bg-stone-500",
  "Music / Media": "bg-fuchsia-500",
  "Video Streaming": "bg-red-500",
  Gaming: "bg-orange-500",
  "System Tools": "bg-zinc-500",
  Other: "bg-neutral-400",
};

const ALL_CATEGORIES = Object.keys(CATEGORY_COLORS);

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

  const loadPending = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchPendingClassifications();
      setSuggestions(data.suggestions);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

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
      const result = await approveClassification(id);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
      showToast(`Applied to ${result.affected_rows} past sessions`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Approve failed");
    }
  };

  const handleReject = async (id: number) => {
    try {
      await rejectClassification(id);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Reject failed");
    }
  };

  const handleEditApprove = async (id: number) => {
    if (!editCategory.trim()) return;
    try {
      const result = await editAndApproveClassification(id, editCategory.trim());
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
      setEditId(null);
      setEditCategory("");
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
          disabled={scanning || trackerNoData}
          className="rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
          title={trackerNoData ? "Start the desktop tracker first" : undefined}
        >
          {scanning ? "Scanning…" : "Scan Uncategorized"}
        </button>
      </div>

      {trackerNoData && (
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
                  <div className="flex items-center gap-1">
                    <select
                      value={editCategory}
                      onChange={(e) => setEditCategory(e.target.value)}
                      aria-label="Select category"
                      className="rounded bg-white/10 border border-white/20 px-2 py-1 text-xs text-white"
                    >
                      <option value="">Pick category…</option>
                      {ALL_CATEGORIES.filter((c) => c !== "Other").map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => handleEditApprove(s.id)}
                      disabled={!editCategory.trim()}
                      className="rounded bg-amber-700/70 px-2 py-1 text-xs text-white hover:bg-amber-600 disabled:opacity-40 transition-colors"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => {
                        setEditId(null);
                        setEditCategory("");
                      }}
                      className="rounded bg-white/10 px-2 py-1 text-xs text-white/60 hover:bg-white/20 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => {
                      setEditId(s.id);
                      setEditCategory(s.suggested_category);
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
