import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import {
  BookMarked,
  CheckCircle2,
  CircleDashed,
  Database,
  Loader2,
  Play,
  RefreshCw,
  Upload,
  AlertCircle,
} from "lucide-react";
import { Button } from "../../app/components/ui/button";
import { cn } from "../../app/components/ui/utils";
import {
  fetchCorpusJob,
  fetchCorpusOverview,
  formatBytes,
  ingestCorpusBook,
  runCorpusSetup,
  uploadCorpusBook,
  type BookSlot,
  type CorpusJob,
  type CorpusOverview,
} from "../../api/corpusClient";
import "../../styles/study-library.css";

const STEPS = [
  "1. Your Books",
  "2. Build Index",
  "3. Done",
] as const;

function BookCard({
  book,
  onUpload,
  onIngest,
  uploading,
  ingesting,
}: {
  book: BookSlot;
  onUpload: (subjectId: string, file: File) => void;
  onIngest: (book: BookSlot) => void;
  uploading: string | null;
  ingesting: string | null;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const status = book.ingested_chunks > 0 ? "indexed" : book.file_present ? "ready" : "missing";

  return (
    <div className="study-library-glass rounded-xl p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-emerald-50">{book.short_label}</p>
          <p className="text-xs text-emerald-200/60 mt-0.5">{book.label}</p>
        </div>
        {status === "indexed" && (
          <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide text-emerald-300 bg-emerald-950/60 px-2 py-0.5 rounded-full">
            <CheckCircle2 className="size-3" />
            Indexed
          </span>
        )}
        {status === "ready" && (
          <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide text-amber-200 bg-amber-950/50 px-2 py-0.5 rounded-full">
            <CircleDashed className="size-3" />
            On disk
          </span>
        )}
        {status === "missing" && (
          <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide text-slate-400 bg-slate-900/60 px-2 py-0.5 rounded-full">
            Missing
          </span>
        )}
      </div>

      <p className="text-xs text-emerald-100/70 leading-relaxed">{book.description}</p>

      <div className="text-[11px] text-emerald-200/50 font-mono truncate" title={book.expected_filename}>
        {book.expected_filename || "—"}
      </div>

      {book.file_present && (
        <p className="text-xs text-emerald-300/80">
          File: {formatBytes(book.file_size_bytes)}
          {book.ingested_chunks > 0 && ` · ${book.ingested_chunks} chunks indexed`}
        </p>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={book.format === "epub" ? ".epub" : ".pdf"}
        className="hidden"
        aria-label={`Upload ${book.short_label}`}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onUpload(book.subject_id, f);
          e.target.value = "";
        }}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="w-full border-emerald-900/50 bg-black/20 text-emerald-100 hover:bg-emerald-950/40"
        disabled={uploading === book.subject_id}
        onClick={() => inputRef.current?.click()}
      >
        {uploading === book.subject_id ? (
          <Loader2 className="size-4 animate-spin mr-2" />
        ) : (
          <Upload className="size-4 mr-2" />
        )}
        {book.file_present ? "Replace book file" : "Upload book"}
      </Button>

      {book.file_present && (
        <Button
          type="button"
          size="sm"
          className="w-full bg-emerald-700 hover:bg-emerald-600 text-white"
          disabled={ingesting === book.subject_id || uploading === book.subject_id}
          onClick={() => onIngest(book)}
        >
          {ingesting === book.subject_id ? (
            <Loader2 className="size-4 animate-spin mr-2" />
          ) : (
            <Play className="size-4 mr-2" />
          )}
          {book.auto_chapters
            ? `Index chapters ${book.auto_chapters.join(", ")}`
            : "Index full book"}
        </Button>
      )}
    </div>
  );
}

export function LibrarySetupPage() {
  const [step, setStep] = useState(0);
  const [overview, setOverview] = useState<CorpusOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<CorpusJob | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [ingesting, setIngesting] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCorpusOverview();
      setOverview(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const pollJob = useCallback(
    (jobId: string, onDone?: () => void) => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const j = await fetchCorpusJob(jobId);
          if (!j) return;
          setJob(j);
          if (j.status === "done" || j.status === "error") {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            await refresh();
            onDone?.();
            if (j.status === "done" && step === 1) setStep(2);
          }
        } catch {
          /* keep polling */
        }
      }, 1500);
    },
    [refresh, step],
  );

  const handleRunSetup = async () => {
    setError(null);
    setStep(1);
    try {
      const started = await runCorpusSetup();
      setJob(started);
      pollJob(started.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Setup failed");
      setStep(0);
    }
  };

  const handleIngestBook = async (book: BookSlot) => {
    setIngesting(book.subject_id);
    setError(null);
    setStep(1);
    try {
      const chapters = book.auto_chapters ?? undefined;
      const started = await ingestCorpusBook(book.subject_id, chapters);
      setJob(started);
      pollJob(started.job_id, () => setIngesting(null));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ingest failed");
      setIngesting(null);
      setStep(0);
    }
  };

  const handleUpload = async (subjectId: string, file: File) => {
    setUploading(subjectId);
    setError(null);
    try {
      await uploadCorpusBook(subjectId, file);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(null);
    }
  };

  const totalChunks = overview?.corpus.total_chunks ?? 0;
  const booksReady = overview?.books.filter((b) => b.ready).length ?? 0;
  const mmlReady = overview?.books.find((b) => b.subject_id === "linear_algebra")?.file_present;

  return (
    <div className="min-h-full study-library-page text-emerald-50">
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        <header className="space-y-2">
          <div className="flex items-center gap-2 text-emerald-300/80 text-sm">
            <Database className="size-4" />
            <span>Knowledge Base Setup</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Turn your books into a searchable brain</h1>
          <p className="text-sm text-emerald-100/70 max-w-2xl leading-relaxed">
            Drop your textbooks and lecture transcripts here. One click builds a local search index —
            MML chapters 1–2 plus whole PDF books on disk — so quizzes, gap analysis, and the AI coach
            can cite real sources.
          </p>
        </header>

        <div className="study-library-glass flex h-12 overflow-hidden p-1">
          {STEPS.map((label, index) => (
            <button
              key={label}
              type="button"
              onClick={() => index < step && setStep(index)}
              className={cn(
                "study-library-step flex-1 flex items-center justify-center text-xs font-medium rounded-lg transition-colors",
                index < step && "hover:bg-white/5 cursor-pointer",
              )}
              data-active={step === index}
            >
              {label}
            </button>
          ))}
        </div>

        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-200">
            <AlertCircle className="size-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {step === 0 && (
          <div className="space-y-6">
            <div className="study-library-glass rounded-xl p-4 flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium">
                  {booksReady} of {overview?.books.length ?? 5} books on disk
                </p>
                <p className="text-xs text-emerald-200/60 mt-1">
                  {totalChunks > 0
                    ? `${totalChunks} chunks indexed — Build refreshes MML, transcripts, and new full PDFs`
                    : "Nothing indexed yet — upload MML first, then click Build"}
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="border-emerald-900/50"
                  onClick={() => void refresh()}
                  disabled={loading}
                >
                  <RefreshCw className={cn("size-4 mr-2", loading && "animate-spin")} />
                  Refresh
                </Button>
                <Button
                  type="button"
                  size="sm"
                  className="bg-emerald-600 hover:bg-emerald-500 text-white"
                  onClick={() => void handleRunSetup()}
                  disabled={!mmlReady || loading || job?.status === "running" || ingesting !== null}
                >
                  <Play className="size-4 mr-2" />
                  Build Knowledge Base
                </Button>
              </div>
            </div>

            {!mmlReady && (
              <p className="text-xs text-amber-200/90 bg-amber-950/30 border border-amber-900/40 rounded-lg px-3 py-2">
                Upload <strong>Mathematics for Machine Learning</strong> (PDF) first — it is the anchor textbook
                for chapter 1–2 indexing.
              </p>
            )}
            {overview?.environment?.pandoc_available === false && (
              <p className="text-xs text-amber-200/80 bg-amber-950/20 border border-amber-900/30 rounded-lg px-3 py-2">
                Install <strong>pandoc</strong> on PATH to ingest EPUB books (Statistics, DS from Scratch, etc.).
              </p>
            )}

            {loading && !overview ? (
              <div className="flex justify-center py-12">
                <Loader2 className="size-8 animate-spin text-emerald-400" />
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {overview?.books.map((book) => (
                  <BookCard
                    key={book.subject_id}
                    book={book}
                    onUpload={(id, f) => void handleUpload(id, f)}
                    onIngest={(b) => void handleIngestBook(b)}
                    uploading={uploading}
                    ingesting={ingesting}
                  />
                ))}
              </div>
            )}

            {overview && overview.transcripts.length > 0 && (
              <div className="study-library-glass rounded-xl p-4 space-y-2">
                <p className="text-sm font-medium flex items-center gap-2">
                  <BookMarked className="size-4 text-emerald-400" />
                  Lecture transcripts (auto-included in build)
                </p>
                <ul className="text-xs text-emerald-200/70 space-y-1">
                  {overview.transcripts.slice(0, 5).map((t) => (
                    <li key={t.filename} className="flex justify-between gap-2 font-mono">
                      <span className="truncate">{t.filename}</span>
                      <span className="shrink-0 text-emerald-300/60">
                        {t.ingested_chunks > 0 ? `${t.ingested_chunks} chunks` : formatBytes(t.size_bytes)}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="text-[11px] text-emerald-200/50">
                  Capture live captions from Lecture Notes — they land in{" "}
                  <code className="text-emerald-300/70">data/transcripts/</code> and get indexed automatically.
                </p>
              </div>
            )}
          </div>
        )}

        {step === 1 && (
          <div className="study-library-glass rounded-xl p-6 space-y-4">
            <div className="flex items-center gap-3">
              {job?.status === "running" || job?.status === "queued" ? (
                <Loader2 className="size-6 animate-spin text-emerald-400" />
              ) : job?.status === "error" ? (
                <AlertCircle className="size-6 text-red-400" />
              ) : (
                <CheckCircle2 className="size-6 text-emerald-400" />
              )}
              <div>
                <p className="text-sm font-medium">Building your knowledge base…</p>
                <p className="text-xs text-emerald-200/60">{job?.message || "Starting…"}</p>
              </div>
            </div>

            <div className="h-2 rounded-full bg-black/40 overflow-hidden">
              <div
                className="h-full bg-emerald-500 transition-all duration-500"
                style={{ width: `${Math.round((job?.progress ?? 0) * 100)}%` }}
              />
            </div>

            <div className="rounded-lg bg-black/40 border border-emerald-900/30 p-3 max-h-64 overflow-y-auto font-mono text-[11px] text-emerald-200/80 space-y-0.5">
              {(job?.logs ?? []).map((line, i) => (
                <div key={`${i}-${line.slice(0, 24)}`}>{line}</div>
              ))}
              {(!job?.logs || job.logs.length === 0) && (
                <div className="text-emerald-200/40">Waiting for log output…</div>
              )}
            </div>

            {job?.status === "error" && (
              <Button type="button" variant="outline" onClick={() => setStep(0)}>
                Back and retry
              </Button>
            )}
          </div>
        )}

        {step === 2 && overview && (
          <div className="space-y-4">
            <div className="study-library-glass rounded-xl p-6 text-center space-y-3">
              <CheckCircle2 className="size-12 text-emerald-400 mx-auto" />
              <h2 className="text-lg font-semibold">Knowledge base is ready</h2>
              <p className="text-sm text-emerald-200/70">
                {overview.corpus.total_chunks} searchable chunks from{" "}
                {overview.corpus.documents.length} sources.
              </p>
              <div className="flex flex-wrap justify-center gap-2 pt-2">
                <Button asChild className="bg-emerald-600 hover:bg-emerald-500">
                  <Link to="/lecture-notes">Open Lecture Notes</Link>
                </Button>
                <Button asChild variant="outline" className="border-emerald-900/50">
                  <Link to="/ai-coach">Ask AI Coach</Link>
                </Button>
                <Button type="button" variant="ghost" onClick={() => setStep(0)}>
                  Back to library
                </Button>
              </div>
            </div>

            <div className="study-library-glass rounded-xl p-4">
              <p className="text-xs font-medium text-emerald-300/80 mb-2">Indexed documents</p>
              <ul className="text-xs space-y-1 text-emerald-200/70">
                {overview.corpus.documents.map((d) => (
                  <li key={d.document_id} className="flex justify-between gap-2">
                    <span>{d.title}</span>
                    <span className="text-emerald-400">{d.chunks} chunks</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
