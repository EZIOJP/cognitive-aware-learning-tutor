import { Camera, Loader2, Sparkles } from "lucide-react";
import { Button } from "../../app/components/ui/button";
import { Input } from "../../app/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../app/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "../../app/components/ui/sheet";
import type { LlmConfig, TranscriptFile } from "../../api/transcriptsClient";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  transcripts: TranscriptFile[];
  selectedTranscript: string;
  onTranscriptChange: (filename: string) => void;
  noteTitle: string;
  onNoteTitleChange: (value: string) => void;
  notesSemantic: boolean;
  onNotesSemanticChange: (value: boolean) => void;
  notesFast: boolean;
  onNotesFastChange: (value: boolean) => void;
  llmConfig: LlmConfig | null;
  generating: boolean;
  snapshotting: boolean;
  onGenerate: () => void;
  onGenerateToday: () => void;
  onSnapshot: () => void;
  referenceHint?: string;
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

export function StudyLibraryCreateSheet({
  open,
  onOpenChange,
  transcripts,
  selectedTranscript,
  onTranscriptChange,
  noteTitle,
  onNoteTitleChange,
  notesSemantic,
  onNotesSemanticChange,
  notesFast,
  onNotesFastChange,
  llmConfig,
  generating,
  snapshotting,
  onGenerate,
  onGenerateToday,
  onSnapshot,
  referenceHint,
}: Props) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[min(420px,92vw)] border-emerald-900/40 bg-slate-950/95">
        <SheetHeader>
          <SheetTitle>Create from live captions</SheetTitle>
          <SheetDescription>
            Pick a transcript, optionally add a title, then generate structured lecture notes into the
            current folder.
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-4 px-1">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-emerald-200/80">Transcript</label>
            <Select value={selectedTranscript} onValueChange={onTranscriptChange}>
              <SelectTrigger className="h-9 text-sm bg-black/30 border-emerald-900/40">
                <SelectValue placeholder="Select transcript" />
              </SelectTrigger>
              <SelectContent>
                {transcripts.map((t) => (
                  <SelectItem key={t.filename} value={t.filename} className="text-sm">
                    {t.filename} ({formatSize(t.size_bytes)})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-emerald-200/80">Note title (optional)</label>
            <Input
              className="h-9 text-sm bg-black/30 border-emerald-900/40"
              value={noteTitle}
              onChange={(e) => onNoteTitleChange(e.target.value)}
              placeholder="e.g. Lecture 3 — NumPy arrays"
            />
          </div>

          <div className="flex flex-col gap-2 text-sm text-emerald-100/80">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={notesFast}
                onChange={(e) => onNotesFastChange(e.target.checked)}
                className="rounded"
              />
              Fast mode (transcript only, fewer LLM calls)
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={notesSemantic}
                onChange={(e) => onNotesSemanticChange(e.target.checked)}
                className="rounded"
              />
              Topic grouping (richer structure, slower)
            </label>
          </div>

          {referenceHint && (
            <p className="text-xs text-emerald-300/70 rounded-lg bg-emerald-950/40 border border-emerald-900/30 px-3 py-2">
              References attached: {referenceHint}
            </p>
          )}

          <div className="flex gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              className="flex-1 border-emerald-800/50"
              disabled={snapshotting || !selectedTranscript}
              onClick={onSnapshot}
            >
              {snapshotting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <Camera className="w-4 h-4 mr-1.5" />
                  Capture slide
                </>
              )}
            </Button>
            <Button
              type="button"
              className="flex-1"
              disabled={generating || !selectedTranscript}
              onClick={onGenerate}
            >
              {generating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-1.5" />
                  Generate
                </>
              )}
            </Button>
          </div>

          <Button
            type="button"
            variant="secondary"
            className="w-full"
            disabled={generating}
            onClick={onGenerateToday}
          >
            Generate from today&apos;s captions
          </Button>

          <p className="text-xs text-muted-foreground pt-2 border-t border-emerald-900/30">
            {llmConfig?.reachable
              ? `LLM ready · ${llmConfig.model}`
              : "Start your local LLM (Ollama / LM Studio) for generation."}
          </p>
        </div>
      </SheetContent>
    </Sheet>
  );
}
