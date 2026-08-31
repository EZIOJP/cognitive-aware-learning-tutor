import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import {
  ArrowLeft,
  Database,
  Loader2,
  Pencil,
  RefreshCw,
  Trash2,
  Wand2,
} from "lucide-react";
import { Badge } from "../../app/components/ui/badge";
import { Button } from "../../app/components/ui/button";
import { Card } from "../../app/components/ui/card";
import { Input } from "../../app/components/ui/input";
import { useAuth } from "../../context/AuthContext";
import {
  deleteTrainSample,
  fetchTrainDuplicates,
  fetchTrainSampleImageBlob,
  fetchTrainSamples,
  postImportMathwriting,
  postRecalibrateStructure,
  postReloadTextellerModel,
  postRetrainStrokeSymbol,
  postRetrainTexteller,
  postTrainDuplicateCleanup,
  updateTrainSample,
  type TrainSampleItem,
} from "../../api/mathClient";

function SampleThumb({ sampleId, hasPng }: { sampleId: string; hasPng: boolean }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    if (!hasPng) return;
    let url: string | null = null;
    void fetchTrainSampleImageBlob(sampleId).then((u) => {
      url = u;
      setSrc(u);
    });
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [sampleId, hasPng]);
  if (!hasPng || !src) return <span className="text-xs text-muted-foreground">—</span>;
  return (
    <img src={src} alt="" className="w-14 h-10 object-contain bg-white rounded border" />
  );
}

export function OcrTrainingDataPage() {
  const { isAuthenticated, sessionReady } = useAuth();
  const [searchParams] = useSearchParams();
  const highlightId = searchParams.get("highlight");
  const [items, setItems] = useState<TrainSampleItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [editLatex, setEditLatex] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retrainBusy, setRetrainBusy] = useState<string | null>(null);
  const [pathsOnly, setPathsOnly] = useState(false);
  const [dupCount, setDupCount] = useState(0);
  const [importBusy, setImportBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const [data, dups] = await Promise.all([
      fetchTrainSamples({ limit: 100, has_paths_json: pathsOnly ? true : undefined }),
      fetchTrainDuplicates(),
    ]);
    if (!data) {
      setError("Could not load training samples.");
      setItems([]);
      setTotal(0);
    } else {
      setItems(data.items);
      setTotal(data.total);
    }
    setDupCount(dups?.total_groups ?? 0);
    setLoading(false);
  }, [pathsOnly]);

  useEffect(() => {
    if (sessionReady && isAuthenticated) void load();
  }, [sessionReady, isAuthenticated, load]);

  useEffect(() => {
    if (!highlightId || loading) return;
    const el = document.getElementById(`sample-${highlightId}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightId, loading, items.length]);

  const cleanupDuplicates = async () => {
    if (!window.confirm("Delete duplicate samples (keep oldest per group)?")) return;
    setBusyId("cleanup");
    const r = await postTrainDuplicateCleanup();
    setBusyId(null);
    if (!r) {
      setError("Cleanup failed.");
      return;
    }
    setMessage(`Removed ${r.deleted} duplicates from ${r.groups_cleaned} groups.`);
    void load();
  };

  const startEdit = (row: TrainSampleItem) => {
    setEditId(row.sample_id);
    setEditLatex(row.confirmed_latex || row.predicted_latex || "");
  };

  const saveEdit = async () => {
    if (!editId) return;
    setBusyId(editId);
    const ok = await updateTrainSample(editId, { confirmed_latex: editLatex });
    setBusyId(null);
    if (!ok) {
      setError("Update failed.");
      return;
    }
    setEditId(null);
    setMessage("Label updated.");
    void load();
  };

  const remove = async (sampleId: string) => {
    if (!window.confirm("Delete this training sample and its PNG/paths? This cannot be undone.")) return;
    setBusyId(sampleId);
    const ok = await deleteTrainSample(sampleId);
    setBusyId(null);
    if (!ok) {
      setError("Delete failed.");
      return;
    }
    setMessage("Sample deleted.");
    void load();
  };

  const runImport = async () => {
    setImportBusy(true);
    setError(null);
    setMessage(null);
    try {
      const r = await postImportMathwriting({ max_samples: 100 });
      if (!r) {
        setError("Import failed — check network and auth.");
        return;
      }
      setMessage(`Imported ${r.imported ?? 0} MathWriting samples (${r.skipped ?? 0} skipped).`);
      void load();
    } finally {
      setImportBusy(false);
    }
  };

  const runRetrain = async (kind: "stroke" | "structure" | "texteller" | "reload") => {
    setRetrainBusy(kind);
    setError(null);
    setMessage(null);
    try {
      if (kind === "stroke") {
        const r = await postRetrainStrokeSymbol();
        setMessage(r?.message || r?.status || "Stroke retrain finished.");
      } else if (kind === "structure") {
        const r = await postRecalibrateStructure();
        setMessage(r?.message || r?.status || "Structure calibration finished.");
      } else if (kind === "reload") {
        const r = await postReloadTextellerModel();
        setMessage(r ? `Model reloaded: ${r.model_id}` : "Reload failed (admin only).");
      } else {
        const r = await postRetrainTexteller("export");
        setMessage(r?.message || r?.status || "TexTeller export finished.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Retrain failed");
    } finally {
      setRetrainBusy(null);
    }
  };

  return (
    <div className="h-full min-h-0 overflow-y-auto p-4 md:p-6">
      <div className="mx-auto max-w-5xl space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link to="/math-tutor" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
              <ArrowLeft className="w-4 h-4" />
              Math Tutor
            </Link>
            <div className="flex items-center gap-2">
              <Database className="w-5 h-5 text-primary" />
              <h1 className="text-xl font-semibold">OCR training data</h1>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={`w-4 h-4 mr-1 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={importBusy}
              onClick={() => void runImport()}
            >
              {importBusy && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
              Import MathWriting
            </Button>
            <Link to="/math-tutor/train">
              <Button size="sm">Collect samples</Button>
            </Link>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <label className="inline-flex items-center gap-1 cursor-pointer">
            <input
              type="checkbox"
              checked={pathsOnly}
              onChange={(e) => setPathsOnly(e.target.checked)}
            />
            paths_json only (stroke retrain)
          </label>
          {dupCount > 0 && (
            <>
              <Badge variant="secondary">{dupCount} duplicate groups</Badge>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void cleanupDuplicates()}>
                Clean duplicates
              </Button>
            </>
          )}
          <span className="text-muted-foreground">{total} samples</span>
        </div>

        <p className="text-sm text-muted-foreground max-w-3xl">
          Separate from the Train Playground: review, fix labels, or delete bad samples before retrain.
          Editable data is better than permanent — wrong labels poison TexTeller and stroke_symbol. Delete
          duplicates and mis-clicks; then run retrain below.
        </p>

        {message && (
          <div className="text-sm border border-primary/30 rounded-lg p-3 bg-primary/5">{message}</div>
        )}
        {error && (
          <div className="text-sm text-destructive border border-destructive/30 rounded-lg p-3">{error}</div>
        )}

        <Card className="gloss-panel p-4 space-y-3">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Wand2 className="w-4 h-4" />
            Apply dataset to models
          </h2>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={!!retrainBusy || total < 3}
              onClick={() => void runRetrain("stroke")}
            >
              {retrainBusy === "stroke" && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
              Retrain stroke disambiguator
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={!!retrainBusy || total < 5}
              onClick={() => void runRetrain("structure")}
            >
              {retrainBusy === "structure" && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
              Recalibrate structure
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={!!retrainBusy || total < 50}
              onClick={() => void runRetrain("texteller")}
            >
              {retrainBusy === "texteller" && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
              Export TexTeller (50+)
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!!retrainBusy}
              onClick={() => void runRetrain("reload")}
            >
              {retrainBusy === "reload" && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
              Reload ONNX model
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            {total} sample{total === 1 ? "" : "s"} in dataset · stroke/structure retrain available to all users
          </p>
        </Card>

        <Card className="gloss-panel overflow-hidden">
          {loading ? (
            <p className="p-6 text-sm text-muted-foreground flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading…
            </p>
          ) : items.length === 0 ? (
            <div className="p-6 text-sm text-muted-foreground space-y-2">
              <p>No training samples yet.</p>
              <Link to="/math-tutor/train" className="text-primary hover:underline">
                Open Train Playground →
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50 text-left text-xs text-muted-foreground">
                    <th className="p-3 w-16">Ink</th>
                    <th className="p-3">Label</th>
                    <th className="p-3">Predicted</th>
                    <th className="p-3">Tier</th>
                    <th className="p-3 w-28">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr
                      key={row.sample_id}
                      id={`sample-${row.sample_id}`}
                      className={`border-b border-border/30 align-top ${
                        highlightId === row.sample_id ? "bg-primary/10 ring-1 ring-primary/30" : ""
                      }`}
                    >
                      <td className="p-3">
                        <SampleThumb sampleId={row.sample_id} hasPng={row.has_png} />
                      </td>
                      <td className="p-3 font-mono text-xs break-all">
                        {editId === row.sample_id ? (
                          <div className="flex flex-col gap-2">
                            <Input value={editLatex} onChange={(e) => setEditLatex(e.target.value)} />
                            <div className="flex gap-2">
                              <Button size="sm" onClick={() => void saveEdit()} disabled={busyId === row.sample_id}>
                                Save
                              </Button>
                              <Button size="sm" variant="ghost" onClick={() => setEditId(null)}>
                                Cancel
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <>
                            {row.confirmed_latex || "—"}
                            <div className="mt-1 flex flex-wrap gap-1">
                              <Badge variant="outline" className="text-[10px]">
                                {row.agree || "?"}
                              </Badge>
                              {row.has_paths_json && (
                                <Badge variant="secondary" className="text-[10px]">
                                  paths
                                </Badge>
                              )}
                            </div>
                          </>
                        )}
                      </td>
                      <td className="p-3 font-mono text-xs text-muted-foreground break-all">
                        {row.predicted_latex || "—"}
                      </td>
                      <td className="p-3 text-xs">
                        {row.tier}
                        {row.prompt_text && (
                          <span className="block text-muted-foreground">{row.prompt_text}</span>
                        )}
                      </td>
                      <td className="p-3">
                        <div className="flex gap-1">
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8"
                            onClick={() => startEdit(row)}
                            disabled={!!busyId}
                            title="Edit label"
                          >
                            <Pencil className="w-4 h-4" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8 text-destructive"
                            onClick={() => void remove(row.sample_id)}
                            disabled={busyId === row.sample_id}
                            title="Delete"
                          >
                            {busyId === row.sample_id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
