import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, FileText, Loader2, RefreshCw } from "lucide-react";
import { Button } from "../../app/components/ui/button";
import { cn } from "../../app/components/ui/utils";
import { fetchLogFiles, fetchLogTail, type LogFileInfo } from "../../api/systemClient";

type Props = {
  /** Which log file to show first */
  defaultFile?: string;
  /** Poll while true (e.g. during note generation or corpus build) */
  live?: boolean;
  pollMs?: number;
  maxLines?: number;
  className?: string;
  title?: string;
  compact?: boolean;
};

export function StudyLibraryLogPanel({
  defaultFile = "backend.log",
  live = false,
  pollMs = 2000,
  maxLines = 200,
  className,
  title = "App logs",
  compact = false,
}: Props) {
  const [files, setFiles] = useState<LogFileInfo[]>([]);
  const [selected, setSelected] = useState(defaultFile);
  const [content, setContent] = useState("");
  const [logsDir, setLogsDir] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickBottom = useRef(true);
  const inFlightRef = useRef(false);
  const selectedRef = useRef(selected);
  const prevSelectedRef = useRef(selected);

  useEffect(() => {
    selectedRef.current = selected;
  }, [selected]);

  const refreshTail = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    const file = selectedRef.current;
    try {
      const tail = await fetchLogTail(file, maxLines);
      if (file !== selectedRef.current) return;
      setContent(tail.content || "(empty log)");
      setError(null);
    } catch (e) {
      if (file !== selectedRef.current) return;
      setError(e instanceof Error ? e.message : "Could not load logs");
    } finally {
      inFlightRef.current = false;
      setLoading(false);
    }
  }, [maxLines]);

  const refreshAll = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setRefreshing(true);
    const file = selectedRef.current;
    try {
      const [list, tail] = await Promise.all([
        fetchLogFiles(true),
        fetchLogTail(file, maxLines),
      ]);
      if (file !== selectedRef.current) return;
      setFiles(list.files.filter((f) => f.exists));
      setLogsDir(list.logs_dir);
      setContent(tail.content || "(empty log)");
      setError(null);
      setReady(true);
    } catch (e) {
      if (file !== selectedRef.current) return;
      setError(e instanceof Error ? e.message : "Could not load logs");
    } finally {
      inFlightRef.current = false;
      setLoading(false);
      setRefreshing(false);
    }
  }, [maxLines]);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    if (!ready) return;
    if (prevSelectedRef.current === selected) return;
    prevSelectedRef.current = selected;
    void refreshTail();
  }, [selected, ready, refreshTail]);

  useEffect(() => {
    if (!live || !ready) return;
    const id = window.setInterval(() => void refreshTail(), pollMs);
    return () => window.clearInterval(id);
  }, [live, pollMs, ready, refreshTail]);

  useEffect(() => {
    if (!stickBottom.current || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [content]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    stickBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
  };

  return (
    <div className={cn("study-library-glass rounded-xl p-4 space-y-3", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-medium text-emerald-50">
          <FileText className="size-4 text-emerald-400" />
          {title}
          {live && (
            <span className="text-[10px] uppercase tracking-wide text-emerald-300/80 bg-emerald-950/50 px-2 py-0.5 rounded-full">
              live
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="h-8 rounded-md border border-emerald-900/50 bg-black/30 px-2 text-xs text-emerald-100"
            aria-label="Log file"
          >
            {files.map((f) => (
              <option key={f.name} value={f.name}>
                {f.name}
              </option>
            ))}
            {files.length === 0 && <option value={selected}>{selected}</option>}
          </select>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 border-emerald-900/50 text-emerald-100"
            onClick={() => void refreshAll()}
            disabled={loading || refreshing}
          >
            {loading || refreshing ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <RefreshCw className="size-3.5" />
            )}
          </Button>
        </div>
      </div>

      {!compact && logsDir && (
        <p className="text-[11px] text-emerald-200/50 font-mono truncate" title={logsDir}>
          Folder: {logsDir}
        </p>
      )}

      {error && (
        <p className="text-xs text-red-300 bg-red-950/30 border border-red-900/40 rounded px-2 py-1">{error}</p>
      )}

      <div
        ref={scrollRef}
        onScroll={onScroll}
        className={cn(
          "rounded-lg bg-black/40 border border-emerald-900/30 p-3 overflow-y-auto font-mono text-[11px] text-emerald-200/80 whitespace-pre-wrap break-words",
          compact ? "max-h-40" : "max-h-72",
        )}
      >
        {loading && !content ? (
          <span className="text-emerald-200/40">Loading log…</span>
        ) : (
          content
        )}
      </div>

      <p className="text-[11px] text-emerald-200/50">
        Tip: open the same files in{" "}
        <code className="text-emerald-300/70">data/logs/</code> from Transcript Notes Studio or your editor.
        {selected === "notes_generation.log" && " — note generation steps land here."}
      </p>
    </div>
  );
}

export function LogPanelOpenFolderHint({ logsDir }: { logsDir?: string }) {
  if (!logsDir) return null;
  return (
    <a
      href={`file:///${logsDir.replace(/\\/g, "/")}`}
      className="inline-flex items-center gap-1 text-xs text-emerald-300/80 hover:text-emerald-200"
      title="Open folder (may be blocked by browser)"
    >
      Open log folder <ExternalLink className="size-3" />
    </a>
  );
}
