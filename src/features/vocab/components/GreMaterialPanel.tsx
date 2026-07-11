import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../../context/AuthContext";
import { authFetch } from "../api/authClient";
import { clearReviewCards } from "../../../api/globalQuizClient";
import { Button } from "../../../app/components/ui/button";
import { Badge } from "../../../app/components/ui/badge";

type Preview = {
  unique_words?: number;
  with_meaning?: number;
  stubs?: number;
  folder?: string;
};

type QueueItem = { id: number; word: string; meaning: string; thin: boolean; has_meaning: boolean };

export function GreMaterialPanel() {
  const { token, isAdmin } = useAuth();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [queueCount, setQueueCount] = useState(0);
  const [queueHead, setQueueHead] = useState<QueueItem[]>([]);
  const [status, setStatus] = useState<{ type: "ok" | "err"; message: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [replace, setReplace] = useState(true);

  const refreshMeta = useCallback(async () => {
    if (!isAdmin || !token) return;
    try {
      const [{ data: prev }, { data: q }] = await Promise.all([
        authFetch("/words/import/gref/preview", token),
        authFetch("/words/enrich-queue?limit=20", token),
      ]);
      setPreview(prev as Preview);
      setQueueCount(Number((q as { count?: number }).count ?? 0));
      setQueueHead(((q as { items?: QueueItem[] }).items ?? []) as QueueItem[]);
    } catch (e) {
      setStatus({
        type: "err",
        message: e instanceof Error ? e.message : "Failed to load GRE import status",
      });
    }
  }, [isAdmin, token]);

  useEffect(() => {
    void refreshMeta();
  }, [refreshMeta]);

  const runImport = async () => {
    if (!isAdmin || !token) return;
    setBusy(true);
    setStatus(null);
    try {
      const { data } = await authFetch("/words/import/gref", token, {
        method: "POST",
        body: JSON.stringify({
          replace,
          reset_progress: true,
          clear_review_cards: true,
        }),
      });
      setStatus({
        type: "ok",
        message:
          `Imported total ${data.total ?? "?"} (added ${data.added ?? 0}, updated ${data.updated ?? 0}). ` +
          `With meaning: ${data.with_meaning ?? "?"}. ` +
          `Progress cleared: ${data.progress_rows_deleted ?? 0}. Review cards cleared: ${data.review_cards_deleted ?? 0}.`,
      });
      await refreshMeta();
    } catch (e) {
      setStatus({ type: "err", message: e instanceof Error ? e.message : "Import failed" });
    } finally {
      setBusy(false);
    }
  };

  const enrichNext = async () => {
    if (!isAdmin || !token || !queueHead[0]) return;
    setBusy(true);
    setStatus(null);
    try {
      const id = queueHead[0].id;
      const { data } = await authFetch(`/words/${id}/enrich?overwrite=false`, token, { method: "POST" });
      const w = (data as { word?: { word?: string; meaning?: string } }).word;
      setStatus({
        type: "ok",
        message: `Enriched ${w?.word ?? id}: ${(w?.meaning ?? "").slice(0, 120)}`,
      });
      await refreshMeta();
    } catch (e) {
      setStatus({ type: "err", message: e instanceof Error ? e.message : "Enrich failed" });
    } finally {
      setBusy(false);
    }
  };

  const enrichBatch = async () => {
    if (!isAdmin || !token) return;
    setBusy(true);
    setStatus(null);
    try {
      const { data } = await authFetch("/words/enrich/batch", token, {
        method: "POST",
        body: JSON.stringify({ limit: 10, overwrite: false }),
      });
      setStatus({
        type: "ok",
        message: `Batch enriched ${data.enriched ?? 0}/${data.requested ?? 0}; remaining thin ~${data.remaining ?? "?"}`,
      });
      await refreshMeta();
    } catch (e) {
      setStatus({ type: "err", message: e instanceof Error ? e.message : "Batch enrich failed" });
    } finally {
      setBusy(false);
    }
  };

  const clearReviews = async () => {
    if (!isAdmin || !token) return;
    setBusy(true);
    setStatus(null);
    try {
      const data = await clearReviewCards();
      setStatus({ type: "ok", message: `Cleared ${data.deleted} review card(s).` });
    } catch (e) {
      setStatus({ type: "err", message: e instanceof Error ? e.message : "Clear failed" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="gloss-panel rounded-2xl p-6 max-w-4xl mb-6">
      <h2 className="text-xl font-semibold mb-2">GRE material bank</h2>
      <p className="text-sm text-muted-foreground mb-4">
        Import all lists from <code>gref_material/gre words/</code> (deduped, Title Case).{" "}
        <strong>Fill empty</strong> only writes missing fields (connotation, mnemonic, examples, etc.) —
        high-priority words first. Quiz only uses words that already have meanings.
      </p>
      {!isAdmin && (
        <p className="text-sm text-amber-700 dark:text-amber-300 mb-3">Admin login required.</p>
      )}
      <div className="flex flex-wrap gap-2 mb-3">
        <Badge variant="outline">unique {preview?.unique_words ?? "—"}</Badge>
        <Badge variant="outline">with meaning {preview?.with_meaning ?? "—"}</Badge>
        <Badge variant="outline">stubs {preview?.stubs ?? "—"}</Badge>
        <Badge variant="outline">enrich queue {queueCount}</Badge>
      </div>
      <label className="flex items-center gap-2 text-sm mb-3">
        <input
          type="checkbox"
          checked={replace}
          onChange={(e) => setReplace(e.target.checked)}
          disabled={!isAdmin || busy}
        />
        Replace entire bank (recommended for first full import)
      </label>
      <div className="flex flex-wrap gap-2">
        <Button type="button" onClick={() => void runImport()} disabled={!isAdmin || busy}>
          {busy ? "Working…" : "Import GRE material"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={() => void enrichNext()}
          disabled={!isAdmin || busy || !queueHead[0]}
        >
          Fill empty next
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={() => void enrichBatch()}
          disabled={!isAdmin || busy || queueCount === 0}
        >
          Fill empty ×10
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => void clearReviews()}
          disabled={!isAdmin || busy}
        >
          Clear review cards
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => void refreshMeta()}
          disabled={!isAdmin || busy}
        >
          Refresh
        </Button>
      </div>
      {queueHead.length > 0 && (
        <p className="text-xs text-muted-foreground mt-3">
          Next: {queueHead.slice(0, 5).map((q) => q.word).join(", ")}
          {queueHead.length > 5 ? "…" : ""}
        </p>
      )}
      {status && (
        <p
          className={`mt-3 text-sm ${status.type === "ok" ? "text-emerald-600" : "text-destructive"}`}
        >
          {status.message}
        </p>
      )}
    </div>
  );
}
