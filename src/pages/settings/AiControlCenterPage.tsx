import { Fragment, useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { ArrowLeft, Brain, ExternalLink, RefreshCw } from "lucide-react";
import { Card } from "../../app/components/ui/card";
import { Button } from "../../app/components/ui/button";
import { Input } from "../../app/components/ui/input";
import { SettingsPageScroll } from "./SettingsPageScroll";
import {
  getLlmConfig,
  getLlmEnvStatus,
  loadLlmPrefs,
  patchLlmKeys,
  saveLlmPrefs,
  testLlmChain,
  testAllRouteProfiles,
  tierForTask,
  type LlmCallRecord,
  type LlmChainTestResult,
  type LlmConfig,
  type LlmEnvStatus,
  type LlmKeysPatch,
  type LlmTestAllProfilesResult,
} from "../../api/transcriptsClient";

const TIERS = ["light", "medium", "heavy"] as const;
type Tier = (typeof TIERS)[number];

const ROUTE_PROFILES = ["hybrid-free", "openrouter", "local", "hybrid", "9router", "max-free-cloud"] as const;

/** Official models / API-format docs for each key provider. */
const KEY_FIELDS: {
  envKey: keyof LlmKeysPatch;
  label: string;
  statusKey: string;
  docsUrl?: string;
  docsLabel?: string;
}[] = [
  {
    envKey: "LLM_CLOUD_API_KEY",
    label: "Gemini (LLM_CLOUD_API_KEY)",
    statusKey: "llm_cloud_api_key",
    docsUrl: "https://ai.google.dev/gemini-api/docs/models",
    docsLabel: "Models",
  },
  {
    envKey: "GEMINI_API_KEY",
    label: "Gemini alias (GEMINI_API_KEY)",
    statusKey: "gemini_api_key",
    docsUrl: "https://ai.google.dev/gemini-api/docs/models",
    docsLabel: "Models",
  },
  {
    envKey: "GROQ_API_KEY",
    label: "Groq (free tier)",
    statusKey: "groq_api_key",
    docsUrl: "https://console.groq.com/docs/models",
    docsLabel: "Models",
  },
  {
    envKey: "CEREBRAS_API_KEY",
    label: "Cerebras (free tier)",
    statusKey: "cerebras_api_key",
    docsUrl: "https://inference-docs.cerebras.ai/models/overview",
    docsLabel: "Models",
  },
  {
    envKey: "MISTRAL_API_KEY",
    label: "Mistral La Plateforme",
    statusKey: "mistral_api_key",
    docsUrl: "https://docs.mistral.ai/getting-started/models/models_overview/",
    docsLabel: "Models",
  },
  {
    envKey: "GITHUB_TOKEN",
    label: "GitHub Models (PAT)",
    statusKey: "github_token",
    docsUrl: "https://docs.github.com/en/github-models/about-github-models",
    docsLabel: "Docs",
  },
  {
    envKey: "LLM_OPENROUTER_API_KEY",
    label: "OpenRouter",
    statusKey: "llm_openrouter_api_key",
    docsUrl: "https://openrouter.ai/docs/api/reference/overview",
    docsLabel: "API format",
  },
  {
    envKey: "LLM_ANTHROPIC_API_KEY",
    label: "Anthropic",
    statusKey: "llm_anthropic_api_key",
    docsUrl: "https://docs.anthropic.com/en/docs/about-claude/models",
    docsLabel: "Models",
  },
  {
    envKey: "NIM_API_KEY",
    label: "NVIDIA NIM",
    statusKey: "nim_api_key",
    docsUrl: "https://docs.api.nvidia.com/nim/reference/llm-apis",
    docsLabel: "API",
  },
  {
    envKey: "LLM_API_KEY",
    label: "Local placeholder (LM Studio)",
    statusKey: "llm_api_key",
    docsUrl: "https://lmstudio.ai/docs/developer",
    docsLabel: "Docs",
  },
  {
    envKey: "TAVILY_API_KEY",
    label: "Tavily (web search)",
    statusKey: "tavily_api_key",
    docsUrl: "https://docs.tavily.com/",
    docsLabel: "Docs",
  },
];

/** Provider → models / API docs (for chain entry links). */
const PROVIDER_DOCS: Record<string, string> = {
  gemini: "https://ai.google.dev/gemini-api/docs/models",
  google: "https://ai.google.dev/gemini-api/docs/models",
  groq: "https://console.groq.com/docs/models",
  cerebras: "https://inference-docs.cerebras.ai/models/overview",
  mistral: "https://docs.mistral.ai/getting-started/models/models_overview/",
  github: "https://docs.github.com/en/github-models/about-github-models",
  openrouter: "https://openrouter.ai/models",
  or: "https://openrouter.ai/models",
  anthropic: "https://docs.anthropic.com/en/docs/about-claude/models",
  nim: "https://docs.api.nvidia.com/nim/reference/llm-apis",
  nvidia: "https://docs.api.nvidia.com/nim/reference/llm-apis",
  lmstudio: "https://lmstudio.ai/docs/developer",
  ollama: "https://ollama.com/library",
};

function providerDocsUrl(provider: string, model?: string): string | null {
  const p = provider.trim().toLowerCase();
  if ((p === "openrouter" || p === "or") && model?.includes("/")) {
    return `https://openrouter.ai/${model}`;
  }
  return PROVIDER_DOCS[p] ?? null;
}

const FEATURE_TASKS = [
  { task: "notes_job", label: "Notes generation" },
  { task: "corpus_grounded", label: "Grounded RAG notes" },
  { task: "quiz_gen", label: "Quiz generation" },
  { task: "coach", label: "AI coach chat" },
  { task: "classify", label: "App classification" },
  { task: "daily_review", label: "Daily review" },
  { task: "math_hint", label: "Math hints" },
  { task: "block_regen", label: "Block repair / regen" },
  { task: "project_agent", label: "Project agent" },
  { task: "vocab_enrich", label: "GRE vocab card enrich" },
  { task: "gap_analysis", label: "Gap analysis" },
] as const;

function tierLabel(tier: Tier): string {
  if (tier === "light") return "Light";
  if (tier === "heavy") return "Heavy";
  return "Medium";
}

function formatTime(iso?: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatCost(cost?: number | null): string {
  if (cost == null) return "—";
  if (cost === 0) return "$0";
  return `$${cost.toFixed(4)}`;
}

function initialDefaultTier(): Tier {
  const stored = loadLlmPrefs().llm_tier;
  if (stored && TIERS.includes(stored as Tier)) return stored as Tier;
  return "medium";
}

export default function AiControlCenterPage() {
  const [defaultTier, setDefaultTier] = useState<Tier>(initialDefaultTier);
  const [taskTiers, setTaskTiers] = useState<Record<string, string>>(
    () => loadLlmPrefs().task_tiers ?? {},
  );
  const [cfg, setCfg] = useState<LlmConfig | null>(null);
  const [env, setEnv] = useState<LlmEnvStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCall, setExpandedCall] = useState<number | null>(null);
  const [keyDrafts, setKeyDrafts] = useState<Partial<Record<keyof LlmKeysPatch, string>>>({});
  const [routeProfile, setRouteProfile] = useState<string>("local");
  const [savingKeys, setSavingKeys] = useState(false);
  const [keySaveMsg, setKeySaveMsg] = useState<string | null>(null);
  const [chainTests, setChainTests] = useState<Record<string, LlmChainTestResult>>({});
  const [testingTier, setTestingTier] = useState<string | null>(null);
  const [profileTests, setProfileTests] = useState<LlmTestAllProfilesResult | null>(null);
  const [testingAllProfiles, setTestingAllProfiles] = useState(false);

  const routeProfiles =
    env?.route_profiles?.length ? env.route_profiles : [...ROUTE_PROFILES];

  const persistPrefs = useCallback((tier: Tier, tiers: Record<string, string>) => {
    saveLlmPrefs({ ...loadLlmPrefs(), llm_tier: tier, task_tiers: tiers });
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [config, envStatus] = await Promise.all([
        getLlmConfig({ llm_tier: defaultTier }),
        getLlmEnvStatus(),
      ]);
      setCfg(config);
      setEnv(envStatus);
      setRouteProfile(envStatus.route_profile || "local");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load AI settings");
    } finally {
      setLoading(false);
    }
  }, [defaultTier]);

  useEffect(() => {
    persistPrefs(defaultTier, taskTiers);
    void refresh();
  }, [defaultTier, taskTiers, persistPrefs, refresh]);

  const setFeatureTier = (task: string, tier: Tier | "default") => {
    setTaskTiers((prev) => {
      const next = { ...prev };
      if (tier === "default") {
        delete next[task];
      } else {
        next[task] = tier;
      }
      return next;
    });
  };

  const saveKeys = async () => {
    setSavingKeys(true);
    setKeySaveMsg(null);
    try {
      const patch: LlmKeysPatch = { LLM_ROUTE_PROFILE: routeProfile };
      for (const { envKey } of KEY_FIELDS) {
        const draft = keyDrafts[envKey];
        if (draft !== undefined && draft !== "") {
          patch[envKey] = draft;
        }
      }
      const updated = await patchLlmKeys(patch);
      setEnv(updated);
      setKeyDrafts({});
      setKeySaveMsg("Saved to .env — settings reloaded.");
      const config = await getLlmConfig({ llm_tier: defaultTier });
      setCfg(config);
    } catch (e) {
      setKeySaveMsg(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSavingKeys(false);
    }
  };

  const runChainTest = async (tier: Tier) => {
    setTestingTier(tier);
    try {
      const result = await testLlmChain({ tier, route_profile: routeProfile });
      setChainTests((prev) => ({ ...prev, [tier]: result }));
    } catch (e) {
      setChainTests((prev) => ({
        ...prev,
        [tier]: { tier, entries: [], reachable: false },
      }));
      setError(e instanceof Error ? e.message : "Chain test failed");
    } finally {
      setTestingTier(null);
    }
  };

  const testAllChains = async () => {
    for (const t of TIERS) {
      await runChainTest(t);
    }
  };

  const runAllProfileTests = async () => {
    setTestingAllProfiles(true);
    setError(null);
    try {
      const result = await testAllRouteProfiles({ task: "generic" });
      setProfileTests(result);
      const active = result.profiles[routeProfile];
      if (active?.tiers) {
        setChainTests(active.tiers);
      }
    } catch (e) {
      setProfileTests(null);
      setError(e instanceof Error ? e.message : "Profile matrix test failed");
    } finally {
      setTestingAllProfiles(false);
    }
  };

  const tierCellClass = (reachable?: boolean) =>
    reachable
      ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400"
      : "bg-destructive/15 text-destructive";

  const calls = (cfg?.last_calls ?? []) as LlmCallRecord[];
  const heavyBudget = cfg?.tiers?.heavy?.budget as
    | { used?: number; cap?: number; exceeded?: boolean }
    | undefined;

  return (
    <SettingsPageScroll className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Brain className="w-6 h-6" />
          <h1 className="text-2xl font-semibold">AI Control Center</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => void refresh()}>
            <RefreshCw className="w-4 h-4 mr-1" />
            Refresh
          </Button>
          <Link to="/settings" className="text-sm text-primary hover:underline inline-flex items-center gap-1">
            <ArrowLeft className="w-4 h-4" />
            Settings
          </Link>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        Manage API keys and route profile below (saved to server <code className="text-xs">.env</code>). Tier
        chains fall back to local LM Studio when cloud providers fail.
      </p>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : null}

      <Card className="gloss-panel p-5 space-y-4">
        <h2 className="font-medium">Recent calls</h2>
        {calls.length === 0 ? (
          <p className="text-sm text-muted-foreground">No gateway calls yet this session.</p>
        ) : (
          <div className="overflow-x-auto -mx-1">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="text-left text-muted-foreground border-b border-border/60">
                  <th className="py-2 pr-3 font-medium">Time</th>
                  <th className="py-2 pr-3 font-medium">Task</th>
                  <th className="py-2 pr-3 font-medium">Tier</th>
                  <th className="py-2 pr-3 font-medium">Provider</th>
                  <th className="py-2 pr-3 font-medium">Latency</th>
                  <th className="py-2 pr-3 font-medium">Tokens</th>
                  <th className="py-2 pr-3 font-medium">Cost</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {[...calls].reverse().map((call, idx) => {
                  const rowKey = `${call.timestamp ?? ""}-${call.task ?? ""}-${idx}`;
                  const isOpen = expandedCall === idx;
                  const err = call.error && call.error !== "none" ? call.error : null;
                  return (
                    <Fragment key={rowKey}>
                      <tr className="border-b border-border/40 align-top">
                        <td className="py-2 pr-3 whitespace-nowrap">{formatTime(call.timestamp)}</td>
                        <td className="py-2 pr-3 font-mono">{call.task ?? "—"}</td>
                        <td className="py-2 pr-3 capitalize">{call.tier ?? "—"}</td>
                        <td className="py-2 pr-3">
                          <span className="font-mono">{call.provider ?? "—"}</span>
                          {call.model ? (
                            <span className="text-muted-foreground block truncate max-w-[140px]">
                              {call.model}
                            </span>
                          ) : null}
                        </td>
                        <td className="py-2 pr-3 whitespace-nowrap">
                          {call.latency_ms != null ? `${call.latency_ms} ms` : "—"}
                        </td>
                        <td className="py-2 pr-3 whitespace-nowrap">
                          {call.total_tokens ?? "—"}
                        </td>
                        <td className="py-2 pr-3 whitespace-nowrap">{formatCost(call.estimated_cost)}</td>
                        <td className="py-2 pr-3">
                          {err ? (
                            <span className="text-destructive">{err}</span>
                          ) : (
                            <span className="text-emerald-600 dark:text-emerald-400">ok</span>
                          )}
                          {call.fallback ? (
                            <span className="text-muted-foreground block">fallback</span>
                          ) : null}
                        </td>
                        <td className="py-2">
                          {(call.prompt_preview || call.response_preview) && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2"
                              onClick={() => setExpandedCall(isOpen ? null : idx)}
                            >
                              {isOpen ? "Hide" : "Preview"}
                            </Button>
                          )}
                        </td>
                      </tr>
                      {isOpen ? (
                        <tr className="border-b border-border/40">
                          <td colSpan={9} className="py-3 px-1 space-y-2 bg-muted/30">
                            {call.prompt_preview ? (
                              <div>
                                <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
                                  Prompt
                                </p>
                                <p className="text-xs whitespace-pre-wrap break-words">{call.prompt_preview}</p>
                              </div>
                            ) : null}
                            {call.response_preview ? (
                              <div>
                                <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
                                  Response
                                </p>
                                <p className="text-xs whitespace-pre-wrap break-words">{call.response_preview}</p>
                              </div>
                            ) : null}
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="gloss-panel p-5 space-y-4">
        <h2 className="font-medium">Default tier</h2>
        <p className="text-sm text-muted-foreground">
          Used when a feature has no per-task override below.
        </p>
        <div className="flex flex-wrap gap-2">
          {TIERS.map((t) => (
            <Button
              key={t}
              type="button"
              size="sm"
              variant={defaultTier === t ? "default" : "outline"}
              onClick={() => setDefaultTier(t)}
            >
              {tierLabel(t)}
            </Button>
          ))}
        </div>
        {heavyBudget?.cap ? (
          <p className="text-sm text-muted-foreground">
            Heavy tier today: {heavyBudget.used ?? 0}/{heavyBudget.cap} calls
            {heavyBudget.exceeded ? " (cap exceeded)" : ""}
          </p>
        ) : null}
      </Card>

      <Card className="gloss-panel p-5 space-y-4">
        <h2 className="font-medium">Per-feature tiers</h2>
        <p className="text-sm text-muted-foreground">
          Override the default tier for specific study features. Server defaults shown in parentheses.
        </p>
        <div className="space-y-3">
          {FEATURE_TASKS.map(({ task, label }) => {
            const effective = tierForTask(task, { llm_tier: defaultTier, task_tiers: taskTiers });
            const serverDefault = env?.task_defaults?.[task] ?? cfg?.task_defaults?.[task] ?? "medium";
            const override = taskTiers[task];
            return (
              <div
                key={task}
                className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 py-2 border-b border-border/40 last:border-0"
              >
                <div className="sm:w-48 shrink-0">
                  <p className="text-sm font-medium">{label}</p>
                  <p className="text-xs text-muted-foreground font-mono">{task}</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <Button
                    type="button"
                    size="sm"
                    variant={!override ? "default" : "outline"}
                    onClick={() => setFeatureTier(task, "default")}
                  >
                    Default ({serverDefault})
                  </Button>
                  {TIERS.map((t) => (
                    <Button
                      key={t}
                      type="button"
                      size="sm"
                      variant={override === t ? "default" : "outline"}
                      onClick={() => setFeatureTier(task, t)}
                    >
                      {tierLabel(t)}
                    </Button>
                  ))}
                </div>
                <span className="text-xs text-muted-foreground sm:ml-auto">
                  Active: <span className="capitalize font-medium">{effective ?? defaultTier}</span>
                </span>
              </div>
            );
          })}
        </div>
      </Card>

      <Card className="gloss-panel p-5 space-y-4">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <h2 className="font-medium">Provider chains</h2>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={testingTier !== null || testingAllProfiles}
              onClick={() => void testAllChains()}
            >
              {testingTier ? `Testing ${testingTier}…` : "Test all tiers"}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={testingTier !== null || testingAllProfiles}
              onClick={() => void runAllProfileTests()}
            >
              {testingAllProfiles ? "Testing all profiles…" : "Test all route profiles"}
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-sm text-muted-foreground">Route profile:</span>
          {routeProfiles.map((p) => (
            <Button
              key={p}
              type="button"
              size="sm"
              variant={routeProfile === p ? "default" : "outline"}
              onClick={() => setRouteProfile(p)}
            >
              {p}
            </Button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Local: {env?.local.provider ?? cfg?.provider} @ {env?.local.base_url ?? cfg?.base_url}
        </p>
        {cfg?.tiers ? (
          <div className="space-y-4 text-sm">
            {TIERS.map((t) => {
              const info = cfg.tiers?.[t];
              const chain = (info?.chain as Array<{ provider: string; model: string; base_url?: string | null }>) ?? [];
              const testResult = chainTests[t];
              return (
                <div key={t} className="border-b border-border/40 pb-3 last:border-0">
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    <span className="font-medium capitalize">{t}</span>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7"
                      disabled={testingTier === t}
                      onClick={() => void runChainTest(t)}
                    >
                      {testingTier === t ? "Testing…" : "Test chain"}
                    </Button>
                    {testResult ? (
                      <span
                        className={
                          testResult.reachable
                            ? "text-emerald-600 dark:text-emerald-400 text-xs"
                            : "text-destructive text-xs"
                        }
                      >
                        {testResult.reachable ? "reachable" : "none reachable"}
                      </span>
                    ) : null}
                  </div>
                  <p className="text-muted-foreground text-xs mb-2 flex flex-wrap items-center gap-x-1 gap-y-1">
                    {chain.length === 0
                      ? "no chain"
                      : chain.map((c, i) => {
                          const docs = providerDocsUrl(c.provider, c.model);
                          const label = `${c.provider}:${c.model}`;
                          return (
                            <Fragment key={`${t}-${i}-${label}`}>
                              {i > 0 ? <span className="text-muted-foreground/60">→</span> : null}
                              {docs ? (
                                <a
                                  href={docs}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-primary hover:underline inline-flex items-center gap-0.5"
                                  title="Open models / API docs"
                                >
                                  {label}
                                  <ExternalLink className="w-3 h-3 opacity-70" />
                                </a>
                              ) : (
                                <span>{label}</span>
                              )}
                            </Fragment>
                          );
                        })}
                  </p>
                  {testResult?.entries?.length ? (
                    <ul className="space-y-1 text-xs">
                      {testResult.entries.map((e, i) => (
                        <li key={`${t}-${i}`} className="flex gap-2 items-start font-mono">
                          <span
                            className={`w-2 h-2 rounded-full shrink-0 mt-1 ${
                              e.reachable ? "bg-emerald-500" : "bg-destructive/70"
                            }`}
                          />
                          <span className="break-all">{e.entry ?? `${e.provider}:${e.model}`}</span>
                          <span className="text-muted-foreground shrink-0">
                            {e.latency_ms != null ? `${e.latency_ms}ms` : ""}
                            {e.error ? ` · ${e.error}` : ""}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : null}
        {profileTests ? (
          <div className="pt-4 border-t border-border/40 space-y-2">
            <p className="text-sm font-medium">Route profile matrix</p>
            <p className="text-xs text-muted-foreground">
              {profileTests.summary.reachable}/{profileTests.summary.total} profiles have at least one
              reachable tier. Active: <span className="font-mono">{profileTests.active_profile}</span>
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th className="py-1 pr-3 font-medium">Profile</th>
                    {TIERS.map((t) => (
                      <th key={t} className="py-1 px-2 font-medium capitalize">
                        {t}
                      </th>
                    ))}
                    <th className="py-1 pl-2 font-medium">Any</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(profileTests.profiles)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([name, row]) => (
                      <tr
                        key={name}
                        className={
                          name === routeProfile ? "bg-primary/5" : undefined
                        }
                      >
                        <td className="py-1 pr-3 font-mono">{name}</td>
                        {TIERS.map((t) => {
                          const tierResult = row.tiers[t];
                          return (
                            <td key={t} className="py-1 px-2">
                              <span
                                className={`inline-block rounded px-2 py-0.5 ${tierCellClass(
                                  tierResult?.reachable,
                                )}`}
                              >
                                {tierResult?.reachable ? "ok" : "—"}
                              </span>
                            </td>
                          );
                        })}
                        <td className="py-1 pl-2">
                          <span
                            className={`inline-block rounded px-2 py-0.5 ${tierCellClass(
                              row.reachable,
                            )}`}
                          >
                            {row.reachable ? "ok" : "—"}
                          </span>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </Card>

      <Card className="gloss-panel p-5 space-y-4">
        <h2 className="font-medium">API keys</h2>
        <p className="text-sm text-muted-foreground">
          Keys already in <code className="text-xs">.env</code> are never shown in these boxes (security).
          A blank field means <span className="text-foreground">keep the saved key</span>. Type a new
          value only to replace. Status below each label comes from the server.
        </p>
        {!env ? (
          <p className="text-sm text-destructive">
            Key status unknown — backend did not respond. If you ran &quot;Test all route
            profiles&quot;, wait for it to finish or restart the API, then click Refresh.
          </p>
        ) : (
          <p className="text-sm">
            <span className="text-emerald-600 dark:text-emerald-400 font-medium">
              {Object.values(env.keys ?? {}).filter((k) => k.configured).length}
            </span>
            <span className="text-muted-foreground">
              {" "}
              of {KEY_FIELDS.length} keys present in .env
            </span>
          </p>
        )}
        <div className="space-y-3">
          {KEY_FIELDS.map(({ envKey, label, statusKey, docsUrl, docsLabel }) => {
            const status = env?.keys?.[statusKey];
            const known = Boolean(env);
            const configured = Boolean(status?.configured);
            return (
              <div key={envKey} className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap text-xs">
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${
                      !known
                        ? "bg-amber-500"
                        : configured
                          ? "bg-emerald-500"
                          : "bg-muted-foreground/40"
                    }`}
                  />
                  <span className="font-medium">{label}</span>
                  <span
                    className={
                      !known
                        ? "text-amber-600 dark:text-amber-400 font-medium"
                        : configured
                          ? "text-emerald-600 dark:text-emerald-400 font-medium"
                          : "text-muted-foreground"
                    }
                  >
                    {!known
                      ? "Status unknown (API unreachable)"
                      : configured
                        ? `Saved in .env${status?.hint ? ` (${status.hint})` : ""}`
                        : "Not configured"}
                  </span>
                  {docsUrl ? (
                    <a
                      href={docsUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-primary hover:underline font-normal inline-flex items-center gap-0.5 ml-auto"
                    >
                      {docsLabel ?? "Docs"}
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  ) : null}
                </div>
                <Input
                  type="password"
                  autoComplete="off"
                  placeholder={
                    configured ? "Leave blank to keep saved key" : "Paste API key to save"
                  }
                  value={keyDrafts[envKey] ?? ""}
                  onChange={(ev) =>
                    setKeyDrafts((prev) => ({ ...prev, [envKey]: ev.target.value }))
                  }
                />
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <Button type="button" disabled={savingKeys} onClick={() => void saveKeys()}>
            {savingKeys ? "Saving…" : "Save keys & profile"}
          </Button>
          {keySaveMsg ? (
            <span className={`text-sm ${keySaveMsg.startsWith("Saved") ? "text-emerald-600" : "text-destructive"}`}>
              {keySaveMsg}
            </span>
          ) : null}
        </div>
      </Card>
    </SettingsPageScroll>
  );
}
