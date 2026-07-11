import { Link } from "react-router";
import { Brain, ChevronRight } from "lucide-react";
import { Card } from "../app/components/ui/card";
import { HubChatPanel } from "../components/hub/HubChatPanel";

export function HubCortexPage() {
  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Brain className="w-6 h-6" />
          <h1 className="text-2xl font-semibold">Cortex Hub</h1>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <Link to="/ai-coach" className="text-muted-foreground hover:text-primary inline-flex items-center gap-1">
            Legacy coach <ChevronRight className="w-4 h-4" />
          </Link>
          <Link to="/settings/ai" className="text-primary hover:underline inline-flex items-center gap-1">
            AI keys & test <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
      <p className="text-sm text-muted-foreground">
        Multi-agent router: study coach, corpus RAG, codebase agent, web search, and ephemeral PDF Q&A. Inspired by
        cortex-ai patterns — runs on your local LLM gateway.
      </p>
      <Card className="gloss-panel p-5">
        <HubChatPanel />
      </Card>
    </div>
  );
}
