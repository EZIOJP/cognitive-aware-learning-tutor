import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { ArrowLeft, Bot, Code2, RefreshCw } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { fetchAgentSnapshot, type AgentSnapshot } from "../api/hubClient";
import { ProjectAgentChat } from "../components/agent/ProjectAgentChat";
import { Button } from "../app/components/ui/button";
import { Card } from "../app/components/ui/card";

export function ProjectAgentPage() {
  const { isAuthenticated } = useAuth();
  const [snapshot, setSnapshot] = useState<AgentSnapshot | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    const snap = await fetchAgentSnapshot(refresh);
    setSnapshot(snap);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!isAuthenticated) {
    return (
      <div className="p-8 max-w-lg mx-auto text-center space-y-4">
        <p className="text-muted-foreground">Sign in to use the Project Agent with codebase access.</p>
        <Button asChild>
          <Link to="/login">Sign in</Link>
        </Button>
      </div>
    );
  }

  const pipeline = snapshot?.study_pipeline;
  const topCss = snapshot?.css_top_classes?.slice(0, 6) ?? [];

  return (
    <div className="h-full flex flex-col min-h-0 p-4 md:p-6 max-w-4xl mx-auto w-full">
      <div className="flex items-center gap-3 mb-4 shrink-0">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/">
            <ArrowLeft className="w-4 h-4 mr-1" />
            Dashboard
          </Link>
        </Button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Code2 className="w-5 h-5 text-primary" />
            Project Agent
          </h1>
          <p className="text-xs text-muted-foreground">
            Gemma reads your repo — pairs with Cursor to finish the app slowly, one task at a time.
          </p>
        </div>
        <Button variant="outline" size="sm" disabled={loading} onClick={() => void load(true)}>
          <RefreshCw className={`w-4 h-4 mr-1 ${loading ? "animate-spin" : ""}`} />
          Rescan
        </Button>
        <Button variant="ghost" size="sm" asChild>
          <Link to="/ai-coach">
            <Bot className="w-4 h-4 mr-1" />
            Study Coach
          </Link>
        </Button>
      </div>

      <div className="grid md:grid-cols-3 gap-3 mb-4 shrink-0">
        <Card className="p-3 md:col-span-1 space-y-2 text-xs">
          <p className="font-medium text-foreground">Lecture pipeline</p>
          {pipeline ? (
            <ul className="space-y-1 text-muted-foreground">
              <li>{pipeline.step1_live_captions ? "✓" : "○"} Live captions scraper</li>
              <li>{pipeline.step2_transcript_to_notes ? "✓" : "○"} Transcript → notes</li>
              <li>→ /lecture-notes → /review</li>
            </ul>
          ) : (
            <p className="text-muted-foreground">Loading…</p>
          )}
        </Card>
        <Card className="p-3 md:col-span-1 space-y-2 text-xs">
          <p className="font-medium text-foreground">Top CSS classes</p>
          <p className="text-muted-foreground leading-relaxed">
            {topCss.length > 0
              ? topCss.map((c) => `${c.class} (${c.count})`).join(", ")
              : "Rescan to index styles"}
          </p>
        </Card>
        <Card className="p-3 md:col-span-1 space-y-2 text-xs">
          <p className="font-medium text-foreground">How to use with Cursor</p>
          <ol className="list-decimal ml-4 text-muted-foreground space-y-1">
            <li>Ask Project Agent for the next task</li>
            <li>Copy its file list into Cursor chat</li>
            <li>Implement one small change</li>
            <li>Rescan and repeat</li>
          </ol>
        </Card>
      </div>

      <Card className="flex-1 flex flex-col min-h-0 p-4">
        <ProjectAgentChat snapshot={snapshot} className="flex-1" />
      </Card>
    </div>
  );
}
