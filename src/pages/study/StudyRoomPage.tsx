import { Link } from "react-router";
import { ArrowLeft, Loader2, MessageCircle, ScanLine } from "lucide-react";
import { useEditor } from "tldraw";
import { Badge } from "../../app/components/ui/badge";
import { Button } from "../../app/components/ui/button";
import { Card } from "../../app/components/ui/card";
import { TldrawMathCanvas } from "../../components/math-canvas";
import { DesmosGraphWidget } from "../../components/widgets/DesmosGraphWidget";
import { useStudyRoomOcr } from "../../study-room/hooks/useStudyRoomOcr";

function StudyRoomTools() {
  const editor = useEditor();
  const { ocrResult, hint, loading, error, recognize, askIntervention, clearHint } =
    useStudyRoomOcr(editor);

  return (
    <div className="absolute top-3 right-3 z-[500] w-[min(100%,320px)] flex flex-col gap-2 pointer-events-auto">
      <Card className="p-3 gloss-panel space-y-2 shadow-lg">
        <div className="flex gap-2 flex-wrap">
          <Button size="sm" variant="outline" disabled={loading} onClick={() => void recognize()}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ScanLine className="w-4 h-4 mr-1" />}
            Recognize
          </Button>
          <Button size="sm" disabled={loading} onClick={() => void askIntervention()}>
            <MessageCircle className="w-4 h-4 mr-1" />
            Ask
          </Button>
        </div>
        {error && <p className="text-xs text-destructive">{error}</p>}
        {ocrResult && (
          <div className="text-xs space-y-1">
            <p className="font-mono font-medium">{ocrResult.latex || "(empty)"}</p>
            <div className="flex gap-1 flex-wrap">
              <Badge variant={ocrResult.incomplete_step ? "destructive" : "secondary"}>
                {ocrResult.incomplete_step ? "incomplete" : "complete"}
              </Badge>
              <Badge variant="outline">conf {(ocrResult.confidence * 100).toFixed(0)}%</Badge>
            </div>
          </div>
        )}
        {hint && (
          <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-2 text-xs space-y-1">
            <p className="font-medium text-amber-700 dark:text-amber-300">Hint bubble</p>
            <p>{hint.hint}</p>
            <p className="font-medium">{hint.question}</p>
            <p className="text-muted-foreground">Snapshot: {hint.session_snapshot_id.slice(0, 8)}…</p>
            <Button size="sm" variant="ghost" className="h-7" onClick={clearHint}>
              Dismiss
            </Button>
          </div>
        )}
      </Card>
      <Card className="p-2 gloss-panel shadow-lg max-h-[220px] overflow-hidden">
        <p className="text-[10px] text-muted-foreground px-1 mb-1">Desmos zone</p>
        <div className="scale-[0.85] origin-top-left w-[118%]">
          <DesmosGraphWidget />
        </div>
      </Card>
    </div>
  );
}

export function StudyRoomPage() {
  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex items-center gap-2 px-2 py-2 shrink-0 border-b border-border/50">
        <Link to="/math-tutor" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
          <ArrowLeft className="w-4 h-4" />
          Math Tutor
        </Link>
        <span className="text-sm font-medium">Study Room</span>
        <span className="text-xs text-muted-foreground">tldraw grid · manual Recognize / Ask</span>
      </div>
      <div className="flex-1 min-h-0 relative study-room-canvas">
        <TldrawMathCanvas persistenceKey="calt-study-room-v1" showGrid>
          <StudyRoomTools />
        </TldrawMathCanvas>
      </div>
    </div>
  );
}
