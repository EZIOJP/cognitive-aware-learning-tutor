import { useEffect, useRef, useState } from "react";
import {
  Activity,
  Apple,
  Camera,
  Loader2,
  Info,
  Plus,
  Scale,
  Search,
  Send,
  Trash2,
  Zap,
} from "lucide-react";
import { Card } from "../../app/components/ui/card";
import {
  FoodSearchHit,
  MealDraftItem,
  NutritionEstimate,
  useNutrition,
} from "./NutritionContext";

const GOALS_KEY = "nutrinode.dailyGoals";

type DailyGoals = { kcal: number; protein_g: number; carbs_g: number; fat_g: number };

const DEFAULT_GOALS: DailyGoals = { kcal: 2200, protein_g: 120, carbs_g: 250, fat_g: 70 };

function loadGoals(): DailyGoals {
  try {
    const raw = localStorage.getItem(GOALS_KEY);
    if (!raw) return DEFAULT_GOALS;
    return { ...DEFAULT_GOALS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_GOALS;
  }
}

function sourceBadge(source?: string) {
  const s = (source || "").toLowerCase();
  const map: Record<string, string> = {
    custom: "bg-violet-500/15 text-violet-400",
    ifct: "bg-emerald-500/15 text-emerald-400",
    local: "bg-sky-500/15 text-sky-400",
    open_food_facts: "bg-amber-500/15 text-amber-400",
    ai: "bg-rose-500/15 text-rose-400",
    fallback: "bg-muted text-muted-foreground",
  };
  return map[s] || "bg-muted text-muted-foreground";
}

export function NutritionPage() {
  const {
    status,
    liveWsEnabled,
    setLiveWsEnabled,
    todayTotals,
    todayMeals,
    searchFoods,
    estimateFood,
    saveCustomFood,
    analyzePhoto,
    confirmMeal,
    deleteMeal,
    runPipeline,
  } = useNutrition();

  const [goals, setGoals] = useState<DailyGoals>(loadGoals);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<FoodSearchHit[]>([]);
  const [searching, setSearching] = useState(false);
  const [weightG, setWeightG] = useState("100");
  const [servings, setServings] = useState("1");
  const [mealType, setMealType] = useState("lunch");
  const [draft, setDraft] = useState<MealDraftItem[]>([]);
  const [selected, setSelected] = useState<FoodSearchHit | null>(null);
  const [lastEstimate, setLastEstimate] = useState<NutritionEstimate | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pipelineInsights, setPipelineInsights] = useState<any>(null);
  const [isRunningPipeline, setIsRunningPipeline] = useState(false);
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const fileRef = useRef<HTMLInputElement>(null);
  const foodInputRef = useRef<HTMLInputElement>(null);
  const blurCloseRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    localStorage.setItem(GOALS_KEY, JSON.stringify(goals));
  }, [goals]);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 1) {
      setHits([]);
      setHighlightIndex(-1);
      return;
    }
    let cancelled = false;
    const t = setTimeout(async () => {
      setSearching(true);
      try {
        const results = await searchFoods(q);
        if (!cancelled) {
          setHits(results);
          setHighlightIndex(results.length ? 0 : -1);
        }
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 150);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [query, searchFoods]);

  const openSuggestions = () => {
    if (blurCloseRef.current) {
      clearTimeout(blurCloseRef.current);
      blurCloseRef.current = null;
    }
    setSuggestOpen(true);
  };

  const closeSuggestions = () => {
    setSuggestOpen(false);
    setHighlightIndex(-1);
  };

  const scheduleCloseSuggestions = () => {
    blurCloseRef.current = setTimeout(() => closeSuggestions(), 120);
  };

  const addFromHit = (hit: FoodSearchHit) => {
    setSelected(hit);
    setQuery(hit.name);
    setHits([]);
    setWeightG(String(hit.default_serving_g || 100));
    setLastEstimate(null);
    closeSuggestions();
    foodInputRef.current?.focus();
  };

  const pickHighlightedOrFirst = () => {
    if (!hits.length) return;
    const idx = highlightIndex >= 0 ? highlightIndex : 0;
    addFromHit(hits[idx]);
  };

  const addToDraft = async () => {
    const name = (selected?.name || query).trim();
    const w = parseFloat(weightG);
    const s = parseFloat(servings) || 1;
    if (!name || !w || w <= 0) {
      setError("Enter a food and weight in grams");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let estimate = lastEstimate;
      if (!estimate || estimate.food_name.toLowerCase() !== name.toLowerCase()) {
        estimate = await estimateFood(name, w);
        setLastEstimate(estimate);
      } else if (Math.abs(w - (estimate as any)._weight) > 0.1) {
        // rescale from per_g if available
        if (estimate.per_g) {
          const pg = estimate.per_g;
          estimate = {
            ...estimate,
            total_kcal: Math.round(w * pg.kcal * 10) / 10,
            protein_g: Math.round(w * pg.p * 10) / 10,
            carbs_g: Math.round(w * pg.c * 10) / 10,
            fat_g: Math.round(w * pg.f * 10) / 10,
            fiber_g: Math.round(w * (pg.fiber || 0) * 10) / 10,
          };
        } else {
          estimate = await estimateFood(name, w);
          setLastEstimate(estimate);
        }
      }
      const item: MealDraftItem = {
        food_name: estimate.food_name || name,
        weight_g: w,
        servings: s,
        macros_source: estimate.macros_source,
        ai_per_g: estimate.macros_source === "ai" ? estimate.per_g : undefined,
        preview: {
          total_kcal: estimate.total_kcal,
          protein_g: estimate.protein_g,
          carbs_g: estimate.carbs_g,
          fat_g: estimate.fat_g,
          fiber_g: estimate.fiber_g,
        },
      };
      setDraft((prev) => [...prev, item]);
      setQuery("");
      setSelected(null);
      setLastEstimate(null);
      setWeightG("100");
      setServings("1");
    } catch (e: any) {
      setError(e?.message || "Could not resolve nutrition");
    } finally {
      setBusy(false);
    }
  };

  const runAiEstimate = async () => {
    const name = query.trim();
    const w = parseFloat(weightG) || 100;
    if (!name) return;
    setBusy(true);
    setError(null);
    try {
      const est = await estimateFood(name, w);
      setLastEstimate(est);
      setSelected(null);
    } catch (e: any) {
      setError(e?.message || "AI estimate failed");
    } finally {
      setBusy(false);
    }
  };

  const saveAiAsCustom = async () => {
    if (!lastEstimate?.per_g) return;
    setBusy(true);
    try {
      await saveCustomFood({
        name: lastEstimate.food_name,
        display_name: lastEstimate.food_name,
        per_g: lastEstimate.per_g,
        default_serving_g: parseFloat(weightG) || 100,
      });
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const sendMeal = async () => {
    if (!draft.length) return;
    setBusy(true);
    setError(null);
    try {
      await confirmMeal(draft, mealType);
      setDraft([]);
    } catch (e: any) {
      setError(e?.message || "Send failed");
    } finally {
      setBusy(false);
    }
  };

  const onPhoto = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const res = await analyzePhoto(file);
      const first = res.items?.[0];
      if (first) {
        setQuery(first.suggested_name);
        setSelected(null);
        if (first.estimated_weight_g) setWeightG(String(Math.round(first.estimated_weight_g)));
      } else {
        setError(res.description || "No foods detected");
      }
    } catch (e: any) {
      setError(e?.message || "Photo analysis failed");
    } finally {
      setBusy(false);
    }
  };

  const handleRunPipeline = async () => {
    setIsRunningPipeline(true);
    const res: any = await runPipeline();
    setPipelineInsights(res.insights);
    setIsRunningPipeline(false);
  };

  const rem = (goal: number, used: number) => Math.max(0, Math.round(goal - used));

  return (
    <div className="h-full overflow-y-auto max-w-5xl mx-auto space-y-6 p-4">
      <header className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Apple className="w-8 h-8 text-emerald-500" />
            NutriNode
          </h1>
          <p className="text-muted-foreground mt-2 text-sm">
            Search IFCT / local foods, AI estimate when missing, multi-item meals.
            <span
              className={`ml-2 px-2 py-0.5 text-xs rounded-full ${
                status === "connected"
                  ? "bg-emerald-500/20 text-emerald-500"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {liveWsEnabled ? status : "live feed off"}
            </span>
          </p>
        </div>
        <label className="flex items-center gap-3 cursor-pointer rounded-xl border border-border/60 px-4 py-3 gloss-panel shrink-0">
          <input
            type="checkbox"
            className="h-4 w-4 accent-emerald-500"
            checked={liveWsEnabled}
            onChange={(e) => setLiveWsEnabled(e.target.checked)}
          />
          <span className="text-sm">
            <span className="font-medium block">Live hardware WebSocket</span>
            <span className="text-muted-foreground text-xs">ESP32 / scale only</span>
          </span>
        </label>
      </header>

      {/* Goal remaining strip */}
      <Card className="p-4 gloss-panel">
        <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
          <h2 className="font-semibold text-sm">Remaining today</h2>
          <div className="flex flex-wrap gap-2 text-xs">
            {(
              [
                ["kcal", "kcal"],
                ["protein_g", "P g"],
                ["carbs_g", "C g"],
                ["fat_g", "F g"],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="flex items-center gap-1 text-muted-foreground">
                {label}
                <input
                  type="number"
                  className="w-16 bg-background border border-border rounded px-1 py-0.5"
                  value={goals[key]}
                  onChange={(e) => setGoals((g) => ({ ...g, [key]: Number(e.target.value) || 0 }))}
                />
              </label>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "kcal", goal: goals.kcal, used: todayTotals?.total_kcal || 0, color: "text-amber-500" },
            { label: "Protein", goal: goals.protein_g, used: todayTotals?.protein_g || 0, color: "text-blue-500" },
            { label: "Carbs", goal: goals.carbs_g, used: todayTotals?.carbs_g || 0, color: "text-emerald-500" },
            { label: "Fat", goal: goals.fat_g, used: todayTotals?.fat_g || 0, color: "text-rose-500" },
          ].map((s) => (
            <div key={s.label} className="rounded-lg border border-border/50 p-3">
              <div className={`text-xs ${s.color}`}>{s.label} left</div>
              <div className="text-xl font-bold">{rem(s.goal, s.used)}</div>
              <div className="text-[10px] text-muted-foreground">
                {Math.round(s.used)} / {s.goal}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Calories", val: todayTotals?.total_kcal || 0, unit: "kcal", icon: Zap, color: "text-amber-500" },
          { label: "Protein", val: todayTotals?.protein_g || 0, unit: "g", icon: Activity, color: "text-blue-500" },
          { label: "Carbs", val: todayTotals?.carbs_g || 0, unit: "g", icon: Activity, color: "text-emerald-500" },
          { label: "Fats", val: todayTotals?.fat_g || 0, unit: "g", icon: Activity, color: "text-rose-500" },
        ].map((stat) => (
          <Card key={stat.label} className="p-4 gloss-panel flex flex-col justify-center">
            <div className="flex items-center gap-2 mb-2 text-muted-foreground">
              <stat.icon className={`w-4 h-4 ${stat.color}`} />
              <span className="text-sm font-medium">{stat.label}</span>
            </div>
            <div className="text-2xl font-bold">
              {Math.round(stat.val)}{" "}
              <span className="text-sm font-normal text-muted-foreground">{stat.unit}</span>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <Card className="p-5 gloss-panel space-y-4 overflow-visible">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-semibold flex items-center gap-2">
                <Search className="w-4 h-4" /> Meal composer
              </h2>
              <select
                value={mealType}
                onChange={(e) => setMealType(e.target.value)}
                className="bg-background border border-border rounded-md px-2 py-1 text-sm"
              >
                <option value="breakfast">Breakfast</option>
                <option value="lunch">Lunch</option>
                <option value="dinner">Dinner</option>
                <option value="snack">Snack</option>
              </select>
            </div>

            <div className="relative">
              <input
                ref={foodInputRef}
                type="text"
                role="combobox"
                aria-expanded={suggestOpen}
                aria-autocomplete="list"
                autoComplete="off"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setSelected(null);
                  openSuggestions();
                }}
                onFocus={openSuggestions}
                onBlur={scheduleCloseSuggestions}
                onKeyDown={(e) => {
                  if (!suggestOpen && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
                    openSuggestions();
                    return;
                  }
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    if (!hits.length) return;
                    setHighlightIndex((i) => (i + 1) % hits.length);
                  } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    if (!hits.length) return;
                    setHighlightIndex((i) => (i <= 0 ? hits.length - 1 : i - 1));
                  } else if (e.key === "Enter" && suggestOpen && hits.length > 0) {
                    e.preventDefault();
                    pickHighlightedOrFirst();
                  } else if (e.key === "Escape") {
                    closeSuggestions();
                  }
                }}
                className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm pr-10"
                placeholder="Start typing food — suggestions appear as you type"
              />
              {searching && (
                <Loader2 className="w-4 h-4 animate-spin absolute right-3 top-2.5 text-muted-foreground" />
              )}
              {suggestOpen && query.trim().length > 0 && (
                <ul
                  role="listbox"
                  className="absolute z-50 mt-1 w-full max-h-56 overflow-y-auto rounded-md border border-border bg-popover text-popover-foreground shadow-lg"
                >
                  {hits.length > 0 ? (
                    hits.map((h, idx) => (
                      <li key={h.id} role="option" aria-selected={idx === highlightIndex}>
                        <button
                          type="button"
                          className={`w-full text-left px-3 py-2 text-sm flex justify-between gap-2 ${
                            idx === highlightIndex ? "bg-muted" : "hover:bg-muted/60"
                          }`}
                          onMouseDown={(e) => e.preventDefault()}
                          onMouseEnter={() => setHighlightIndex(idx)}
                          onClick={() => addFromHit(h)}
                        >
                          <span>
                            <span className="font-medium capitalize">{h.name}</span>
                            <span className="text-xs text-muted-foreground ml-2">{h.group}</span>
                            <span className="text-xs text-muted-foreground ml-2">
                              {Math.round(h.per_100g.kcal)} kcal/100g
                            </span>
                          </span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${sourceBadge(h.source)}`}>
                            {h.source}
                          </span>
                        </button>
                      </li>
                    ))
                  ) : searching ? (
                    <li className="px-3 py-2 text-sm text-muted-foreground">Searching…</li>
                  ) : (
                    <li className="px-3 py-2 text-sm text-muted-foreground">
                      No matches — press <strong>AI estimate</strong> or keep typing
                    </li>
                  )}
                </ul>
              )}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <label className="text-xs text-muted-foreground">
                Weight (g)
                <input
                  type="number"
                  value={weightG}
                  onChange={(e) => setWeightG(e.target.value)}
                  className="mt-1 w-full bg-background border border-border rounded-md px-2 py-1.5 text-sm"
                />
              </label>
              <label className="text-xs text-muted-foreground">
                Servings
                <input
                  type="number"
                  step="0.5"
                  value={servings}
                  onChange={(e) => setServings(e.target.value)}
                  className="mt-1 w-full bg-background border border-border rounded-md px-2 py-1.5 text-sm"
                />
              </label>
              <button
                type="button"
                onClick={() => void addToDraft()}
                disabled={busy}
                className="sm:col-span-1 self-end bg-primary text-primary-foreground py-2 rounded-md text-sm font-medium flex items-center justify-center gap-1"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Add
              </button>
              <button
                type="button"
                onClick={() => void runAiEstimate()}
                disabled={busy || !query.trim()}
                className="self-end bg-secondary text-secondary-foreground py-2 rounded-md text-sm font-medium"
              >
                AI estimate
              </button>
            </div>

            <div className="flex flex-wrap gap-2">
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={(e) => void onPhoto(e.target.files?.[0])}
              />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                disabled={busy}
                className="text-sm px-3 py-1.5 rounded-md border border-border flex items-center gap-1.5 hover:bg-muted/40"
              >
                <Camera className="w-4 h-4" /> Photo suggest
              </button>
              {lastEstimate?.macros_source === "ai" && lastEstimate.per_g && (
                <button
                  type="button"
                  onClick={() => void saveAiAsCustom()}
                  className="text-sm px-3 py-1.5 rounded-md border border-violet-500/40 text-violet-400"
                >
                  Save as custom food
                </button>
              )}
            </div>

            {lastEstimate && (
              <div className="rounded-md border border-border/60 p-3 text-sm space-y-1">
                <div className="flex justify-between">
                  <span className="font-medium capitalize">{lastEstimate.food_name}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${sourceBadge(lastEstimate.macros_source)}`}>
                    {lastEstimate.macros_source}
                  </span>
                </div>
                <div className="text-muted-foreground text-xs">
                  {Math.round(lastEstimate.total_kcal)} kcal · P {lastEstimate.protein_g}g · C{" "}
                  {lastEstimate.carbs_g}g · F {lastEstimate.fat_g}g · Fiber {lastEstimate.fiber_g}g
                </div>
                {lastEstimate.notes && <p className="text-xs text-muted-foreground">{lastEstimate.notes}</p>}
              </div>
            )}

            {error && <p className="text-sm text-rose-400">{error}</p>}

            {draft.length > 0 && (
              <div className="space-y-2 border-t border-border/50 pt-3">
                <h3 className="text-sm font-medium">Draft ({draft.length} items)</h3>
                {draft.map((it, idx) => (
                  <div
                    key={`${it.food_name}-${idx}`}
                    className="flex justify-between items-center text-sm rounded-md border border-border/40 px-3 py-2"
                  >
                    <div>
                      <div className="font-medium capitalize">{it.food_name}</div>
                      <div className="text-xs text-muted-foreground">
                        {it.weight_g}g · {it.servings} serving
                        {it.servings === 1 ? "" : "s"} · {Math.round(it.preview?.total_kcal || 0)} kcal
                      </div>
                    </div>
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-rose-400"
                      onClick={() => setDraft((d) => d.filter((_, i) => i !== idx))}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => void sendMeal()}
                  disabled={busy}
                  className="w-full bg-emerald-600 hover:bg-emerald-500 text-white py-2.5 rounded-md text-sm font-medium flex items-center justify-center gap-2"
                >
                  {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  Send meal
                </button>
              </div>
            )}
          </Card>

          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Scale className="w-5 h-5" /> Today&apos;s log
          </h2>
          <div className="space-y-3">
            {todayMeals.length === 0 ? (
              <Card className="p-8 text-center text-muted-foreground border-dashed">
                No meals logged today yet.
              </Card>
            ) : (
              todayMeals.map((meal) => (
                <Card key={meal.meal_id} className="p-4 gloss-panel flex justify-between items-start gap-3">
                  <div>
                    <h3 className="font-semibold capitalize text-lg">{meal.food_item}</h3>
                    <div className="text-xs text-muted-foreground flex flex-wrap items-center gap-2 mt-1">
                      {meal.meal_type && (
                        <span className="bg-primary/10 text-primary px-2 py-0.5 rounded-full">{meal.meal_type}</span>
                      )}
                      <span className={`px-2 py-0.5 rounded-full ${sourceBadge(meal.macros_source)}`}>
                        {meal.macros_source || meal.source}
                      </span>
                      <span>{meal.weight_g}g</span>
                      {meal.servings != null && <span>· {meal.servings} srv</span>}
                      <span>·</span>
                      <span>
                        {new Date(meal.timestamp).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      P {Math.round(meal.protein_g)} · C {Math.round(meal.carbs_g)} · F{" "}
                      {Math.round(meal.fat_g)} · Fiber {Math.round(meal.fiber_g || 0)}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="font-bold text-lg text-amber-500">{Math.round(meal.total_kcal)} kcal</div>
                    <button
                      type="button"
                      className="mt-2 text-xs text-muted-foreground hover:text-rose-400 flex items-center gap-1 ml-auto"
                      onClick={() => void deleteMeal(meal.meal_id)}
                    >
                      <Trash2 className="w-3 h-3" /> Delete
                    </button>
                  </div>
                </Card>
              ))
            )}
          </div>
        </div>

        <div className="space-y-6">
          <Card className="p-5 gloss-panel">
            <h3 className="font-semibold mb-2">Data pipeline</h3>
            <p className="text-xs text-muted-foreground mb-4">
              Weekly aggregation for anomalies and top foods.
            </p>
            <button
              onClick={handleRunPipeline}
              disabled={isRunningPipeline}
              className="w-full bg-secondary text-secondary-foreground py-2 rounded-md text-sm font-medium hover:bg-secondary/80 transition-colors flex justify-center items-center gap-2"
            >
              {isRunningPipeline ? <Loader2 className="w-4 h-4 animate-spin" /> : <Activity className="w-4 h-4" />}
              Generate insights
            </button>

            {pipelineInsights && (
              <div className="mt-4 pt-4 border-t border-border/50 text-sm">
                <div className="flex items-center gap-2 text-emerald-400 font-medium mb-2">
                  <Info className="w-4 h-4" /> Weekly summary
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Total calories:</span>
                    <span>{Math.round(pipelineInsights.weekly_totals?.total_kcal || 0)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Top food:</span>
                    <span className="capitalize">{pipelineInsights.top_foods?.[0]?.[0] || "N/A"}</span>
                  </div>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
