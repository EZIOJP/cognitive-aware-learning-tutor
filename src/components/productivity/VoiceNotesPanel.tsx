import { useCallback, useEffect, useState } from "react";
import { Download, Loader2, Mic, RefreshCw } from "lucide-react";
import {
  downloadVoiceNote,
  fetchVoiceNotes,
  type VoiceNoteRow,
} from "../../api/behaviorClient";
import { HUB_REFRESH_EVENT } from "../../utils/dataPipelineBus";

function fmtWhen(ts: number): string {
  if (!ts) return "—";
  try {
    return new Date(ts * 1000).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

function fmtSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function labelFromName(name: string): string {
  const m = /^voice_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/.exec(name);
  return m ? `${m[2]}-${m[3]} ${m[4]}:${m[5]}` : name;
}

export function VoiceNotesPanel() {
  const [notes, setNotes] = useState<VoiceNoteRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [watching, setWatching] = useState(true);

  const refresh = useCallback(async () => {
    setError(null);
    setBusy(true);
    try {
      setNotes(await fetchVoiceNotes());
    } catch (e) {
      setNotes([]);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onHub = () => void refresh();
    window.addEventListener(HUB_REFRESH_EVENT, onHub);
    return () => window.removeEventListener(HUB_REFRESH_EVENT, onHub);
  }, [refresh]);

  useEffect(() => {
    if (!watching) return;
    const id = window.setInterval(() => void refresh(), 12_000);
    return () => window.clearInterval(id);
  }, [watching, refresh]);

  const onDownload = async (name: string) => {
    setError(null);
    setDownloading(name);
    try {
      await downloadVoiceNote(name);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-foreground">
            <Mic size={16} className="text-teal-400/90" />
            CALT Voice clips
          </div>
          <p className="mt-1 max-w-xl text-xs text-muted-foreground leading-relaxed">
            On the watch: record → swipe left → <strong>Files</strong> → tap a clip to send.
            Clips land in <code className="text-[11px]">data/voice_notes/</code> via the hub; download
            them here once the transfer shows <em>Stored on …</em> on the watch.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={watching}
              onChange={(e) => setWatching(e.target.checked)}
              className="rounded border-white/20"
            />
            Auto-refresh
          </label>
          <button
          type="button"
          disabled={busy}
          onClick={() => void refresh()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
        >
          {busy ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <RefreshCw size={12} />
          )}
          Refresh
        </button>
        </div>
      </div>

      {error && <p className="text-xs text-rose-300 break-words">{error}</p>}

      {!busy && notes.length === 0 && !error && (
        <p className="text-xs text-muted-foreground">
          No clips yet. On the watch: record → swipe left → Files → tap a clip to send
          while the desktop tracker is running.
        </p>
      )}

      {notes.length > 0 && (
        <ul className="divide-y divide-white/5 rounded-xl border border-white/10 overflow-hidden">
          {notes.map((note) => (
            <li
              key={note.name}
              className="flex items-center justify-between gap-3 bg-black/20 px-3 py-2.5"
            >
              <div className="min-w-0">
                <div className="truncate text-sm text-foreground">
                  {labelFromName(note.name)}
                </div>
                <div className="text-[11px] text-muted-foreground">
                  {fmtSize(note.size)} · {fmtWhen(note.mtime)}
                </div>
              </div>
              <button
                type="button"
                disabled={downloading === note.name}
                onClick={() => void onDownload(note.name)}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
              >
                {downloading === note.name ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <Download size={12} />
                )}
                Download
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default VoiceNotesPanel;
