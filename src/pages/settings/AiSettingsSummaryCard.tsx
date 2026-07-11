import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { Brain, ChevronRight } from "lucide-react";
import { Card } from "../../app/components/ui/card";
import { getLlmConfig, loadLlmPrefs, type LlmCallRecord } from "../../api/transcriptsClient";

function formatTime(iso?: string): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function AiSettingsSummaryCard() {
  const [lastCall, setLastCall] = useState<LlmCallRecord | null>(null);
  const [reachable, setReachable] = useState<boolean | null>(null);
  const tier = loadLlmPrefs().llm_tier ?? "medium";

  const refresh = useCallback(async () => {
    try {
      const cfg = await getLlmConfig({ llm_tier: tier });
      const calls = (cfg.last_calls ?? []) as LlmCallRecord[];
      setLastCall(calls.length ? calls[calls.length - 1] : null);
      setReachable(cfg.reachable ?? null);
    } catch {
      setLastCall(null);
      setReachable(null);
    }
  }, [tier]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <Card className="gloss-panel p-5 space-y-3">
      <div className="flex items-center gap-2">
        <Brain className="w-5 h-5" />
        <h2 className="font-medium">AI / LLM gateway</h2>
      </div>
      <p className="text-sm text-muted-foreground">
        Default tier: <span className="capitalize font-medium text-foreground">{tier}</span>
        {reachable != null && (
          <>
            {" · "}
            <span className={reachable ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}>
              {reachable ? "provider reachable" : "no provider reachable"}
            </span>
          </>
        )}
      </p>
      {lastCall ? (
        <p className="text-xs text-muted-foreground">
          Last call: {lastCall.task ?? "?"} via {lastCall.provider ?? "?"} —{" "}
          {lastCall.error && lastCall.error !== "none" ? lastCall.error : "ok"}
          {lastCall.timestamp ? ` · ${formatTime(lastCall.timestamp)}` : ""}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">No recent gateway calls.</p>
      )}
      <Link
        to="/settings/ai"
        className="text-sm text-primary hover:underline inline-flex items-center gap-1"
      >
        Open AI Control Center
        <ChevronRight className="w-4 h-4" />
      </Link>
    </Card>
  );
}
