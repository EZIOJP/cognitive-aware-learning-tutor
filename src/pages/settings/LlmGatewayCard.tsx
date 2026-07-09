import { useCallback, useEffect, useState } from "react";
import { Brain, RefreshCw } from "lucide-react";
import { Card } from "../../app/components/ui/card";
import { Button } from "../../app/components/ui/button";
import { getLlmConfig, loadLlmPrefs, saveLlmPrefs, type LlmConfig } from "../../api/transcriptsClient";

const TIERS = ["light", "medium", "heavy"] as const;
type Tier = (typeof TIERS)[number];

function initialTier(): Tier {
  const stored = loadLlmPrefs().llm_tier;
  if (stored && TIERS.includes(stored as Tier)) return stored as Tier;
  return "medium";
}

function tierLabel(tier: Tier): string {
  if (tier === "light") return "Light (local)";
  if (tier === "heavy") return "Heavy (paid cloud)";
  return "Medium (cloud → local)";
}

export function LlmGatewayCard() {
  const [tier, setTier] = useState<Tier>(initialTier);
  const [cfg, setCfg] = useState<LlmConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getLlmConfig({ llm_tier: tier });
      setCfg(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load LLM config");
    } finally {
      setLoading(false);
    }
  }, [tier]);

  useEffect(() => {
    saveLlmPrefs({ ...loadLlmPrefs(), llm_tier: tier });
    void refresh();
  }, [tier, refresh]);

  const heavyBudget = cfg?.tiers?.heavy?.budget as { used?: number; cap?: number } | undefined;

  return (
    <Card className="gloss-panel p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Brain className="w-5 h-5" />
        <h2 className="font-medium">AI / LLM gateway</h2>
      </div>
      <p className="text-sm text-muted-foreground">
        Tier chains try cloud providers first, then fall back to local LM Studio. API keys stay in server{" "}
        <code className="text-xs">.env</code> only.
      </p>

      <div>
        <p className="text-sm font-medium mb-2">Default tier</p>
        <div className="flex flex-wrap gap-2">
          {TIERS.map((t) => (
            <Button
              key={t}
              type="button"
              size="sm"
              variant={tier === t ? "default" : "outline"}
              onClick={() => setTier(t)}
            >
              {tierLabel(t)}
            </Button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Checking providers…</p>
      ) : error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : cfg ? (
        <div className="space-y-2 text-sm">
          <p className="text-xs text-muted-foreground">
            Route profile: <span className="font-medium">{cfg.route_profile || "hybrid"}</span>
          </p>
          {TIERS.map((t) => {
            const info = cfg.tiers?.[t];
            const dot = info?.reachable ? "bg-emerald-500" : "bg-muted-foreground/40";
            const chain = (info?.chain as Array<{ provider: string; model: string }>) ?? [];
            return (
              <div key={t} className="flex gap-2 items-start">
                <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${dot}`} />
                <div>
                  <span className="font-medium capitalize">{t}</span>
                  <span className="text-muted-foreground">
                    {" "}
                    — {chain.map((c) => `${c.provider}:${c.model}`).join(" → ") || "no chain"}
                  </span>
                </div>
              </div>
            );
          })}
          {heavyBudget && heavyBudget.cap ? (
            <p className="text-muted-foreground pt-1">
              Heavy tier today: {heavyBudget.used ?? 0}/{heavyBudget.cap} calls
            </p>
          ) : null}
          {cfg.last_call ? (
            <div className="text-xs text-muted-foreground space-y-1">
              <p>
                Last call: {String((cfg.last_call as { provider?: string }).provider ?? "?")} (
                {String((cfg.last_call as { error?: string }).error ?? "none")})
              </p>
              <p>
                Fallback: {Boolean((cfg.last_call as { fallback?: boolean }).fallback) ? "yes" : "no"}
                {" · "}
                Tokens:{" "}
                {String((cfg.last_call as { total_tokens?: number }).total_tokens ?? "n/a")}
                {" · "}
                Cost:{" "}
                {String((cfg.last_call as { estimated_cost?: number }).estimated_cost ?? "n/a")}
              </p>
            </div>
          ) : null}
        </div>
      ) : null}

      <Button type="button" variant="outline" size="sm" onClick={() => void refresh()}>
        <RefreshCw className="w-4 h-4 mr-1" />
        Refresh
      </Button>
    </Card>
  );
}
