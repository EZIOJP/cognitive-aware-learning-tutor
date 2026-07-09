import { ExternalLink, Router } from "lucide-react";
import { Card } from "../../app/components/ui/card";
import { Button } from "../../app/components/ui/button";

const DASHBOARD = "http://localhost:20128/dashboard";
const API = "http://localhost:20128/v1";

export function NineRouterCard() {
  return (
    <Card className="gloss-panel p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Router className="w-5 h-5" />
        <h2 className="font-medium">9Router (Cursor + free AI)</h2>
      </div>
      <p className="text-sm text-muted-foreground">
        Local gateway for unlimited coding sessions (v0.5.20+). RTK saves 20–40% tokens; combos
        auto-fallback subscription → cheap → free. Runs outside this app on port 20128.
      </p>

      <div className="rounded-md border border-border/60 bg-muted/30 p-3 text-sm space-y-2">
        <p>
          <span className="font-medium">API:</span>{" "}
          <code className="text-xs">{API}</code>
        </p>
        <p>
          <span className="font-medium">Install:</span>{" "}
          <code className="text-xs">scripts\9router\install_9router.bat</code>
        </p>
        <p>
          <span className="font-medium">Start:</span>{" "}
          <code className="text-xs">scripts\9router\start_9router.bat</code>
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="default" asChild>
          <a href={DASHBOARD} target="_blank" rel="noreferrer">
            <ExternalLink className="w-4 h-4 mr-1" />
            Open dashboard
          </a>
        </Button>
        <Button type="button" size="sm" variant="outline" asChild>
          <a href="https://github.com/decolua/9router" target="_blank" rel="noreferrer">
            <ExternalLink className="w-4 h-4 mr-1" />
            9Router on GitHub
          </a>
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">
        Setup: <code className="text-xs">docs/9ROUTER_SETUP.md</code>. Free tiers (2026): connect{" "}
        <strong>Kiro</strong> (<code className="text-xs">kr/</code>) and{" "}
        <strong>OpenCode Free</strong> (<code className="text-xs">oc/</code>) — iFlow/Qwen free
        tiers are discontinued. Create a <code className="text-xs">free-forever</code> combo in the
        dashboard, copy the API key, point Cursor at the API URL. Optional CALT routing: copy{" "}
        <code className="text-xs">data/llm_tiers.9router.example.json</code> →{" "}
        <code className="text-xs">data/llm_tiers.json</code>, set{" "}
        <code className="text-xs">LLM_API_KEY</code> in <code className="text-xs">.env</code>.
      </p>
    </Card>
  );
}
